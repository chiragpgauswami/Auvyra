import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.models.content import StructuredScript
from backend.app.services.content_service import ContentService

def test_structured_script_model():
    script_data = {
        "title": "5 Secret AI Productivity Hacks",
        "hooks": [
            "Stop wasting hours on repetitive tasks every single day.",
            "You are doing AI completely wrong in 2026."
        ],
        "hook_scores": {
            "Stop wasting hours on repetitive tasks every single day.": 92.5,
            "You are doing AI completely wrong in 2026.": 88.0
        },
        "selected_hook": "Stop wasting hours on repetitive tasks every single day.",
        "outline": [
            "Point 1: Automate file sorting",
            "Point 2: Meeting transcription",
            "Point 3: Batch replies"
        ],
        "final_script": "Stop wasting hours on repetitive tasks every single day. First, automate your file sorting. Second, use transcription for meetings. Third, batch your email replies. Subscribe for daily AI workflows that save you 10 hours a week.",
        "cta": "Subscribe for daily AI workflows that save you 10 hours a week."
    }
    structured = StructuredScript(**script_data)
    assert structured.title == "5 Secret AI Productivity Hacks"
    assert "Stop wasting" in structured.selected_hook
    assert len(structured.hooks) == 2
    assert structured.hook_scores[structured.selected_hook] == 92.5
    assert "Subscribe" in structured.cta
    assert len(structured.outline) == 3
    assert len(structured.final_script.split()) > 15

@pytest.mark.asyncio
async def test_content_service_rewrite_script():
    mock_db = MagicMock()
    mock_ai = MagicMock()

    # Mock Script doc in DB
    existing_script = {
        "_id": "507f1f77bcf86cd799439011",
        "user_id": "user_123",
        "channel_id": "channel_456",
        "title": "Old Draft Title",
        "script_text": "This is an old slow boring draft.",
        "duration_estimate": 45,
        "word_count": 7,
        "version": 1,
        "status": "draft",
        "history": []
    }

    mock_script_repo = MagicMock()
    mock_script_repo.find_by_id = AsyncMock(return_value=existing_script)
    mock_script_repo.update_one = AsyncMock(return_value=True)

    mock_brain_repo = MagicMock()
    mock_brain_repo.find_by_channel = AsyncMock(return_value={
        "channel_id": "channel_456",
        "niche": "Tech",
        "tone": "high energy",
        "winning_hooks": ["Stop doing X"],
        "learned_rules": []
    })

    service = ContentService(db=mock_db, ai_gateway=mock_ai)
    service.script_repo = mock_script_repo
    service.brain_repo = mock_brain_repo

    # Mock AI rewrite response
    rewritten_mock = StructuredScript(
        title="Punchy Fast AI Script",
        hooks=["Stop wasting 10 hours a week."],
        selected_hook="Stop wasting 10 hours a week.",
        outline=["Fast hack 1", "Fast hack 2"],
        cta="Follow for more.",
        final_script="Stop wasting 10 hours a week. Automate your workflow now. Follow for more."
    )
    mock_ai.rewrite_structured_script = AsyncMock(return_value=rewritten_mock)

    result = await service.rewrite_script(
        user_id="user_123",
        script_id="507f1f77bcf86cd799439011",
        instruction="Make it punchier"
    )

    assert result["version"] == 2
    assert result["title"] == "Punchy Fast AI Script"
    assert "Stop wasting 10 hours a week" in result["script_text"]
    assert len(result["history"]) == 1
    assert result["history"][0]["version"] == 1
    assert result["history"][0]["instruction"] == "Make it punchier"
    mock_script_repo.update_one.assert_called_once()
