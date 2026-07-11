"""
Central configuration for the Text-to-SQL app.
Override any of these with environment variables of the same name.
"""
import os

# --- LLM (Llama via Ollama) ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3.1")          # e.g. llama3.1, llama3, llama3.1:8b
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "700"))

# --- Embeddings (semantic / vector matching) ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# --- Retrieval sizes ---
TOP_K_TABLES = int(os.getenv("TOP_K_TABLES", "4"))          # how many schema tables to inject into prompt
TOP_K_HISTORY = int(os.getenv("TOP_K_HISTORY", "3"))        # how many past NL->SQL examples to inject

# --- Database (the DB being queried in natural language) ---
DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "database", "sample.db"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "200"))

# --- Paths ---
BASE_DIR = os.path.dirname(__file__)
BUSINESS_CONTEXT_PATH = os.path.join(BASE_DIR, "data", "business_context.json")
QUERY_HISTORY_PATH = os.path.join(BASE_DIR, "data", "query_history.json")
EMBEDDING_CACHE_PATH = os.path.join(BASE_DIR, "data", "embedding_cache.pkl")

# --- Safety ---
# Only read-only statements are allowed to be executed against the database.
ALLOWED_SQL_PREFIXES = ("SELECT", "WITH")
BLOCKED_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "ATTACH", "PRAGMA", "GRANT", "REVOKE"
)
