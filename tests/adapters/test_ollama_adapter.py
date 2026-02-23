import httpx

from apps.adapters.ollama_adapter import OllamaAdapter, OllamaConfig


def _adapter_with_transport(handler):
    transport = httpx.MockTransport(handler)
    adapter = OllamaAdapter(
        OllamaConfig(
            base_url="http://test-ollama",
            chat_model="llama3",
            embed_model="nomic-embed-text",
            timeout=2,
            max_retries=0,
        )
    )
    adapter._client = httpx.Client(base_url=adapter.config.base_url, transport=transport, timeout=2)
    return adapter


def test_chat_uses_tools_and_normalizes_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "model": "llama3",
                "message": {"role": "assistant", "content": "ok", "tool_calls": []},
                "done": True,
            },
        )

    adapter = _adapter_with_transport(handler)
    tools = [{"type": "function", "function": {"name": "save_preference", "parameters": {"type": "object"}}}]

    response = adapter.chat(messages=[{"role": "user", "content": "hello"}], tools=tools)

    assert response["message"]["content"] == "ok"
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/chat"
    assert '"tools"' in captured["payload"]


def test_embed_falls_back_to_legacy_endpoint():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/embed":
            return httpx.Response(500, json={"error": "unsupported"})
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    adapter = _adapter_with_transport(handler)
    result = adapter.embed(["offline text"])

    assert result["count"] == 1
    assert result["data"][0]["embedding"] == [0.1, 0.2, 0.3]
    assert calls == ["/api/embed", "/api/embeddings"]
