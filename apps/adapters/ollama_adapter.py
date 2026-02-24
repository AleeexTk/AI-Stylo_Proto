import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional

import httpx


class OllamaAdapterError(Exception):
    """Base adapter error."""


class OllamaServerUnavailableError(OllamaAdapterError):
    """Raised when the Ollama server is unavailable."""


class OllamaModelNotFoundError(OllamaAdapterError):
    """Raised when the configured model does not exist on the server."""


class OllamaTimeoutError(OllamaAdapterError):
    """Raised when request timed out."""


class OllamaInvalidResponseError(OllamaAdapterError):
    """Raised when server returned malformed payload."""


@dataclass
class OllamaConfig:
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3")
    embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "30"))
    max_retries: int = 2
    retry_backoff_s: float = 0.5


class OllamaAdapter:
    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._timeout = httpx.Timeout(self.config.timeout)
        self._client = httpx.Client(base_url=self.config.base_url, timeout=self._timeout)

    def close(self) -> None:
        self._client.close()

    def health(self) -> Dict[str, Any]:
        tags = self._request_json("GET", "/api/tags")
        models = [m.get("name", "") for m in tags.get("models", []) if isinstance(m, dict)]

        chat_ok = self._model_exists(self.config.chat_model, models)
        embed_ok = self._model_exists(self.config.embed_model, models)

        status = "ok" if chat_ok and embed_ok else "degraded"
        if not chat_ok:
            raise OllamaModelNotFoundError(
                f"Chat model '{self.config.chat_model}' is missing on Ollama server."
            )
        if not embed_ok:
            raise OllamaModelNotFoundError(
                f"Embed model '{self.config.embed_model}' is missing on Ollama server."
            )

        return {
            "status": status,
            "base_url": self.config.base_url,
            "models": {
                "chat": self.config.chat_model,
                "embed": self.config.embed_model,
                "available": models,
            },
        }

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.config.chat_model,
            "messages": messages,
            "stream": False,
        }
        if tools is not None:
            payload["tools"] = tools
        if options is not None:
            payload["options"] = options

        raw = self._request_json("POST", "/api/chat", json_payload=payload)
        return self._normalize_chat_response(raw)

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "model": self.config.chat_model,
            "messages": messages,
            "stream": True,
        }
        if tools is not None:
            payload["tools"] = tools
        if options is not None:
            payload["options"] = options

        attempts = 0
        while True:
            try:
                with self._client.stream("POST", "/api/chat", json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise OllamaInvalidResponseError(
                                "Invalid JSON in streaming response."
                            ) from exc
                        yield self._normalize_chat_chunk(chunk)
                return
            except httpx.TimeoutException as exc:
                if attempts >= self.config.max_retries:
                    raise OllamaTimeoutError("Ollama chat_stream request timed out.") from exc
            except httpx.ConnectError as exc:
                if attempts >= self.config.max_retries:
                    raise OllamaServerUnavailableError(
                        f"Cannot connect to Ollama at {self.config.base_url}."
                    ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise OllamaModelNotFoundError(
                        f"Chat model '{self.config.chat_model}' not found."
                    ) from exc
                raise OllamaAdapterError(f"HTTP error: {exc.response.status_code}") from exc

            attempts += 1
            time.sleep(self.config.retry_backoff_s * attempts)

    def embed(self, texts: Iterable[str]) -> Dict[str, Any]:
        vectors: List[List[float]] = []
        for text in texts:
            payload = {"model": self.config.embed_model, "input": text}
            try:
                raw = self._request_json("POST", "/api/embed", json_payload=payload)
                embedding = raw.get("embeddings", [])
                if embedding and isinstance(embedding[0], list):
                    vectors.append(embedding[0])
                else:
                    raise OllamaInvalidResponseError("Missing embeddings in /api/embed response.")
            except OllamaModelNotFoundError:
                raise
            except OllamaAdapterError:
                legacy_raw = self._request_json(
                    "POST",
                    "/api/embeddings",
                    json_payload={"model": self.config.embed_model, "prompt": text},
                )
                legacy_embedding = legacy_raw.get("embedding")
                if not isinstance(legacy_embedding, list):
                    raise OllamaInvalidResponseError(
                        "Missing embedding in legacy /api/embeddings response."
                    )
                vectors.append(legacy_embedding)

        return {
            "model": self.config.embed_model,
            "data": [{"index": idx, "embedding": vector} for idx, vector in enumerate(vectors)],
            "count": len(vectors),
        }

    def _request_json(
        self,
        method: str,
        path: str,
        json_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        attempts = 0
        while True:
            try:
                response = self._client.request(method, path, json=json_payload)
                response.raise_for_status()
                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    raise OllamaInvalidResponseError("Invalid JSON response from Ollama.") from exc
                if not isinstance(data, dict):
                    raise OllamaInvalidResponseError("Unexpected response format from Ollama.")
                return data
            except httpx.TimeoutException as exc:
                if attempts >= self.config.max_retries:
                    raise OllamaTimeoutError("Ollama request timed out.") from exc
            except httpx.ConnectError as exc:
                if attempts >= self.config.max_retries:
                    raise OllamaServerUnavailableError(
                        f"Cannot connect to Ollama at {self.config.base_url}."
                    ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise OllamaModelNotFoundError("Requested Ollama model or endpoint was not found.") from exc
                raise OllamaAdapterError(f"HTTP error: {exc.response.status_code}") from exc

            attempts += 1
            time.sleep(self.config.retry_backoff_s * attempts)

    @staticmethod
    def _model_exists(required: str, available: List[str]) -> bool:
        required = required.strip()
        return any(name == required or name.startswith(f"{required}:") for name in available)

    def _normalize_chat_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        message = raw.get("message", {}) if isinstance(raw.get("message"), dict) else {}
        return {
            "id": raw.get("created_at"),
            "object": "chat.completion",
            "model": raw.get("model", self.config.chat_model),
            "message": {
                "role": message.get("role", "assistant"),
                "content": message.get("content", ""),
                "tool_calls": message.get("tool_calls", []),
            },
            "done": raw.get("done", True),
            "usage": {
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
            },
            "raw": raw,
        }

    def _normalize_chat_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        message = chunk.get("message", {}) if isinstance(chunk.get("message"), dict) else {}
        return {
            "object": "chat.completion.chunk",
            "model": chunk.get("model", self.config.chat_model),
            "delta": {
                "role": message.get("role", "assistant"),
                "content": message.get("content", ""),
                "tool_calls": message.get("tool_calls", []),
            },
            "done": chunk.get("done", False),
            "raw": chunk,
        }
