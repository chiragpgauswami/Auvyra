import pytest
from backend.app.ai.gateway import AIGateway, repair_json_string, OllamaUnavailableError
from backend.app.models.content import StructuredScript

def test_json_repair_logic():
    # Markdown enclosed
    raw_markdown = "Here is the response:\n```json\n{\"topic\": \"AI Tools\", \"confidence\": 0.9,}\n```\nHope that helps!"
    repaired = repair_json_string(raw_markdown)
    assert repaired == '{"topic": "AI Tools", "confidence": 0.9}'

    # Raw bracket enclosed with trailing commas
    raw_trailing = '{"items": ["a", "b", "c",], "status": "ok",}'
    repaired2 = repair_json_string(raw_trailing)
    assert repaired2 == '{"items": ["a", "b", "c"], "status": "ok"}'

@pytest.mark.asyncio
async def test_ollama_unreachable_exception():
    # Intentionally point to an unreachable port
    gateway = AIGateway(base_url="http://localhost:59999", model="llama3.1:8b")
    with pytest.raises(OllamaUnavailableError) as exc_info:
        await gateway._chat("system prompt", "user prompt")
    
    assert exc_info.value.code == "OLLAMA_UNAVAILABLE"
    assert "unavailable" in exc_info.value.message.lower()

