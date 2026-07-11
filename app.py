"""
FastAPI app: serves the minimal web UI and the text-to-SQL API.

Run:
    python core/db_setup.py     # one-time: create the sample database
    uvicorn app:app --reload
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core.query_generator import QueryGenerator, SQLSafetyError
from core.llm_client import LLMError

BASE_DIR = os.path.dirname(__file__)

app = FastAPI(title="Text-to-SQL (Llama)")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

generator: QueryGenerator | None = None


@app.on_event("startup")
def startup():
    global generator
    # Building indices touches the embedding model, so do it once at startup
    # rather than on every request.
    generator = QueryGenerator()


class QueryRequest(BaseModel):
    question: str


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/schema")
def get_schema():
    return JSONResponse(generator.schema_manager.get_schema_overview())


@app.get("/api/history")
def get_history():
    return JSONResponse(generator.history_manager.get_all()[::-1])


@app.post("/api/query")
def run_query(payload: QueryRequest):
    question = payload.question.strip()
    if not question:
        return JSONResponse({"error": "Please enter a question."}, status_code=400)

    try:
        result = generator.generate(question)
        return JSONResponse(result)
    except SQLSafetyError as e:
        return JSONResponse({"error": f"Safety check failed: {e}"}, status_code=400)
    except LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"Could not run query: {e}"}, status_code=500)
