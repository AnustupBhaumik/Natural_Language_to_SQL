"""
Thin wrapper around a local Llama model served by Ollama
(https://ollama.com). Keeping this isolated means swapping the model or
inference backend later only touches this one file.

Setup (one-time):
    1. Install Ollama: https://ollama.com/download
    2. Pull a Llama model:  `ollama pull llama3.1`
    3. Make sure the Ollama service is running (it runs as a background
       service on most installs, or `ollama serve`).
"""
import ollama

import config


class LLMError(RuntimeError):
    pass


class LlamaClient:
    def __init__(self, model: str = None, host: str = None):
        self.model = model or config.LLAMA_MODEL
        self.client = ollama.Client(host=host or config.OLLAMA_HOST)

    def generate_sql(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={
                    "temperature": config.LLM_TEMPERATURE,
                    "num_predict": config.LLM_MAX_TOKENS,
                },
            )
            return response["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001 - surface a clear, actionable error
            raise LLMError(
                f"Could not reach Llama model '{self.model}' via Ollama at "
                f"{config.OLLAMA_HOST}. Is Ollama running and is the model pulled? "
                f"(`ollama pull {self.model}`). Original error: {exc}"
            ) from exc
