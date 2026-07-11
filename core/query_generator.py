"""
Orchestrates the full text-to-SQL pipeline:

  natural language question
        |
        v
  1. semantic retrieval  -> relevant schema tables (content linking)
                          -> similar past queries (query experience)
        |
        v
  2. prompt assembly      -> schema + business context + few-shot examples
        |
        v
  3. LLM generation (Llama via Ollama)
        |
        v
  4. SQL safety validation (read-only enforcement)
        |
        v
  5. execution against the database
        |
        v
  6. persist to query history for future retrieval
"""
import re
import time
from typing import List

import sqlparse
from sqlalchemy import create_engine, text as sql_text

import config
from core.history_manager import HistoryManager
from core.llm_client import LlamaClient
from core.schema_manager import SchemaManager
from core.vector_store import VectorIndex

SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class SQLSafetyError(ValueError):
    pass


class QueryGenerator:
    def __init__(self):
        self.schema_manager = SchemaManager()
        self.history_manager = HistoryManager()
        self.llm = LlamaClient()
        self.engine = create_engine(config.DATABASE_URL)

        self.schema_index = VectorIndex()
        self.history_index = VectorIndex()
        self.rebuild_indices()

    # ------------------------------------------------------------------ #
    # Index management
    # ------------------------------------------------------------------ #
    def rebuild_indices(self):
        """(Re)build both semantic indices. Call after schema or history changes."""
        self.schema_index.build(self.schema_manager.get_retrieval_documents())
        self.history_index.build(self.history_manager.get_documents_for_index())

    # ------------------------------------------------------------------ #
    # Prompt construction
    # ------------------------------------------------------------------ #
    def _build_prompt(self, question: str, tables: List[str], examples: List[dict]) -> tuple:
        schema_text = self.schema_manager.get_prompt_schema(tables)

        examples_text = ""
        if examples:
            blocks = []
            for ex in examples:
                blocks.append(f"Q: {ex['question']}\nSQL:\n{ex['sql']}")
            examples_text = "\n\n".join(blocks)

        system_prompt = (
            "You are an expert SQLite analyst. Convert the user's natural-language "
            "question into a single, correct, read-only SQL query.\n"
            "Rules:\n"
            "- Only use the tables and columns provided in the schema below.\n"
            "- Only generate SELECT (or WITH ... SELECT) statements. Never modify data.\n"
            "- Follow the business rules given for each table exactly (e.g. what "
            "'revenue' or 'active customer' means).\n"
            "- Prefer explicit JOINs with clear ON conditions.\n"
            "- Return ONLY the SQL query, no explanation, no markdown fences.\n"
        )

        user_prompt = f"SCHEMA:\n{schema_text}\n"
        if examples_text:
            user_prompt += f"\nEXAMPLES OF PAST QUESTIONS AND THEIR SQL (for style/pattern reference):\n{examples_text}\n"
        user_prompt += f"\nQUESTION:\n{question}\n\nSQL:"

        return system_prompt, user_prompt

    # ------------------------------------------------------------------ #
    # SQL cleanup & safety
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_sql(raw: str) -> str:
        fenced = SQL_FENCE_RE.findall(raw)
        candidate = fenced[0].strip() if fenced else raw.strip()
        candidate = candidate.strip().rstrip(";").strip() + ";"
        return candidate

    @staticmethod
    def _validate_sql(sql: str):
        statements = sqlparse.parse(sql)
        if not statements:
            raise SQLSafetyError("The model did not return a parseable SQL statement.")
        if len(statements) > 1:
            raise SQLSafetyError("Only a single SQL statement is allowed.")

        upper = sql.upper()
        if not upper.strip().startswith(config.ALLOWED_SQL_PREFIXES):
            raise SQLSafetyError(
                "Generated statement is not read-only (must start with SELECT or WITH)."
            )
        for kw in config.BLOCKED_KEYWORDS:
            if re.search(rf"\b{kw}\b", upper):
                raise SQLSafetyError(f"Generated SQL contains a blocked keyword: {kw}")

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def _execute_sql(self, sql: str) -> dict:
        with self.engine.connect() as conn:
            result = conn.execute(sql_text(sql))
            columns = list(result.keys())
            rows = [list(r) for r in result.fetchmany(config.MAX_RESULT_ROWS)]
        return {"columns": columns, "rows": rows}

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def generate(self, question: str) -> dict:
        start = time.time()

        # 1. Content linking: semantic retrieval of relevant tables & past queries
        table_matches = self.schema_index.search(question, top_k=config.TOP_K_TABLES)
        tables = [t_id for t_id, _text, _score in table_matches]

        history_matches = self.history_index.search(question, top_k=config.TOP_K_HISTORY)
        examples = []
        for h_id, _text, score in history_matches:
            entry = self.history_manager.get_by_id(h_id)
            if entry and score > 0.3:  # ignore weak / irrelevant matches
                examples.append(entry)

        # 2 + 3. Prompt assembly + LLM generation
        system_prompt, user_prompt = self._build_prompt(question, tables, examples)
        raw_output = self.llm.generate_sql(system_prompt, user_prompt)
        sql = self._clean_sql(raw_output)

        # 4. Safety validation
        self._validate_sql(sql)

        # 5. Execution
        exec_result = self._execute_sql(sql)

        # 6. Persist to history + refresh the history index so it's searchable next time
        self.history_manager.add_entry(question, sql, tables)
        self.history_index.build(self.history_manager.get_documents_for_index())

        elapsed_ms = round((time.time() - start) * 1000)

        return {
            "question": question,
            "sql": sql,
            "columns": exec_result["columns"],
            "rows": exec_result["rows"],
            "row_count": len(exec_result["rows"]),
            "tables_used": [
                {"table": t_id, "relevance": round(score, 3)} for t_id, _text, score in table_matches
            ],
            "similar_past_queries": [
                {"question": e["question"], "sql": e["sql"]} for e in examples
            ],
            "elapsed_ms": elapsed_ms,
        }
