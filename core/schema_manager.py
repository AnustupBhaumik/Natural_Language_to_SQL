"""
Schema Understanding layer.

Responsibilities:
1. Introspect the live database (tables, columns, types, primary/foreign keys)
   using SQLAlchemy so this works against SQLite, Postgres, MySQL, etc.
2. Merge that raw structure with curated "business context" (plain-English
   descriptions, synonyms, business rules) from data/business_context.json.
3. Produce two kinds of text artifacts:
   - "retrieval documents": one per table, written in natural language, used
     to build the semantic (vector) index so we can find relevant tables for
     an arbitrary question.
   - "prompt schema": compact DDL-like text (with business notes) injected
     into the LLM prompt for the tables that were actually retrieved.
"""
import json
import os
from typing import Dict, List

from sqlalchemy import create_engine, inspect

import config


class SchemaManager:
    def __init__(self, database_url: str = None, business_context_path: str = None):
        self.engine = create_engine(database_url or config.DATABASE_URL)
        self.inspector = inspect(self.engine)
        self.business_context = self._load_business_context(
            business_context_path or config.BUSINESS_CONTEXT_PATH
        )
        self.tables: Dict[str, dict] = self._introspect()

    # ------------------------------------------------------------------ #
    # Loading / introspection
    # ------------------------------------------------------------------ #
    def _load_business_context(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)

    def _introspect(self) -> Dict[str, dict]:
        tables = {}
        for table_name in self.inspector.get_table_names():
            columns = self.inspector.get_columns(table_name)
            pk = self.inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            fks = self.inspector.get_foreign_keys(table_name)

            business = self.business_context.get(table_name, {})
            column_ctx = business.get("columns", {})

            tables[table_name] = {
                "name": table_name,
                "description": business.get("description", ""),
                "synonyms": business.get("synonyms", []),
                "business_rules": business.get("business_rules", []),
                "primary_key": pk,
                "foreign_keys": [
                    {
                        "columns": fk["constrained_columns"],
                        "ref_table": fk["referred_table"],
                        "ref_columns": fk["referred_columns"],
                    }
                    for fk in fks
                ],
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                        "description": column_ctx.get(col["name"], ""),
                    }
                    for col in columns
                ],
            }
        return tables

    def refresh(self):
        """Re-run introspection, e.g. after schema changes."""
        self.inspector = inspect(self.engine)
        self.tables = self._introspect()

    # ------------------------------------------------------------------ #
    # Documents for the vector index (semantic / content linking)
    # ------------------------------------------------------------------ #
    def get_retrieval_documents(self) -> List[dict]:
        """One natural-language document per table, used for embedding & search."""
        docs = []
        for table_name, t in self.tables.items():
            column_bits = [
                f"{c['name']} ({c['type']}){': ' + c['description'] if c['description'] else ''}"
                for c in t["columns"]
            ]
            text = (
                f"Table {table_name}. {t['description']} "
                f"Also known as: {', '.join(t['synonyms']) if t['synonyms'] else 'n/a'}. "
                f"Columns: {'; '.join(column_bits)}. "
                f"Business rules: {' '.join(t['business_rules']) if t['business_rules'] else 'none'}."
            )
            docs.append({"id": table_name, "text": text})
        return docs

    # ------------------------------------------------------------------ #
    # Compact schema text for LLM prompt (only for selected tables)
    # ------------------------------------------------------------------ #
    def get_prompt_schema(self, table_names: List[str]) -> str:
        blocks = []
        for name in table_names:
            t = self.tables.get(name)
            if not t:
                continue
            col_lines = []
            for c in t["columns"]:
                flags = []
                if c["name"] in t["primary_key"]:
                    flags.append("PK")
                for fk in t["foreign_keys"]:
                    if c["name"] in fk["columns"]:
                        flags.append(f"FK -> {fk['ref_table']}.{fk['ref_columns'][0]}")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                desc = f" -- {c['description']}" if c["description"] else ""
                col_lines.append(f"    {c['name']} {c['type']}{flag_str}{desc}")

            rules = (
                "\n".join(f"  * {r}" for r in t["business_rules"])
                if t["business_rules"] else "  (none)"
            )
            block = (
                f"TABLE {name}  -- {t['description']}\n"
                + "\n".join(col_lines)
                + f"\n  Business rules for {name}:\n{rules}"
            )
            blocks.append(block)
        return "\n\n".join(blocks)

    def get_all_table_names(self) -> List[str]:
        return list(self.tables.keys())

    def get_schema_overview(self) -> dict:
        """JSON-serialisable overview for the /api/schema endpoint / UI."""
        return self.tables
