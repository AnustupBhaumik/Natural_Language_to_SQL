# Text-to-SQL Generator (Llama-powered)

A local, self-contained Text-to-SQL system: type a question in plain English in
the web UI, and it turns it into SQL, runs it against the database, and shows
you the results — with full transparency into *why* it picked the tables and
prior queries it did.

## How it works

```
User question
     │
     ▼
┌─────────────────────────┐   Vector search over table docs
│ Schema understanding    │──▶ enriched with business_context.json
│ (core/schema_manager.py)│   (descriptions, synonyms, business rules)
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐   Vector search over past (question → SQL)
│ Query experience / RAG  │──▶ pairs stored in data/query_history.json
│ (core/history_manager.py│   (few-shot examples for the LLM)
│  + core/vector_store.py)│
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Prompt assembly          │  schema + business rules + few-shot examples
│ (core/query_generator.py)│  + the question
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Llama (via Ollama)       │  generates the SQL
│ (core/llm_client.py)     │
└─────────────────────────┘
     │
     ▼
Safety check (read-only only) → Execute on DB → Show results + save to history
```

**Semantic matching / content linking** is done with `sentence-transformers`
(`all-MiniLM-L6-v2` by default) — every table (enriched with business context)
and every past query is embedded, and cosine similarity is used to pull only
the *relevant* context into the prompt for a given question. This keeps
prompts small and accurate as the schema and history grow, and it's exactly
the mechanism used for both "schema understanding" and "past query
experience" retrieval.

## Project layout

```
text2sql/
├── app.py                     FastAPI app (web UI + API)
├── config.py                  All settings in one place
├── requirements.txt
├── core/
│   ├── schema_manager.py      DB introspection + business context merge
│   ├── vector_store.py        Embedding-based semantic search
│   ├── history_manager.py     Past query storage/retrieval
│   ├── llm_client.py          Llama (Ollama) client
│   ├── query_generator.py     Orchestrates the full pipeline
│   └── db_setup.py            Creates the sample SQLite database
├── data/
│   ├── business_context.json  Table/column descriptions, synonyms, rules
│   └── query_history.json     Seed past-query examples
├── static/                    CSS + JS for the web UI
└── templates/index.html       The web UI page
```

## Setup

### 1. Install Ollama and pull a Llama model
```bash
# Install from https://ollama.com/download, then:
ollama pull llama3.1
```
Make sure Ollama is running (it runs as a background service after install,
or start it manually with `ollama serve`).

### 2. Install Python dependencies
```bash
cd text2sql
python -m venv venv && source venv/bin/activate    # optional but recommended
pip install -r requirements.txt
```

### 3. Create the sample database
```bash
python core/db_setup.py
```
This creates `database/sample.db` — a small e-commerce schema (customers,
products, orders, order_items) with seed data, so the app works out of the
box.

### 4. Run the app
```bash
uvicorn app:app --reload
```
Open **http://localhost:8000** in your browser.

## Connecting your own database

Point the app at any SQLAlchemy-supported database by setting an environment
variable before starting the app:

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/mydb"
uvicorn app:app --reload
```

Then add entries for your tables to `data/business_context.json` (description,
column meanings, synonyms, and business rules like "revenue = only completed
orders"). This is the single biggest lever for generation accuracy — the LLM
is only as good as the business context you give it.

## Configuration

All tunables live in `config.py` (overridable via environment variables of the
same name), including:
- `LLAMA_MODEL` — which Ollama model to use
- `EMBEDDING_MODEL` — which sentence-transformers model for semantic search
- `TOP_K_TABLES` / `TOP_K_HISTORY` — how much context to retrieve per query
- `MAX_RESULT_ROWS` — cap on rows returned to the UI

## Safety

Only `SELECT` / `WITH ... SELECT` statements are allowed. Any generated SQL
containing `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, etc. is rejected
before execution (see `QueryGenerator._validate_sql`). For production use,
also run the app against a read-only database user/role as defense in depth.
