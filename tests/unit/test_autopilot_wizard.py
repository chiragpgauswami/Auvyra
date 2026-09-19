import pytest
import zoneinfo
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError

from backend.app.models.channel import (
    AutopilotMode,
    ContentFormat,
    PublishSchedule,
    AutopilotConfig,
    NicheRecommendation
)
from backend.app.ai.gateway import AIGateway
from backend.app.services.channel_service import ChannelService


@pytest.mark.asyncio
async def test_niche_recommendations_ollama_success():
    """Verify Ollama returns structured NicheRecommendation objects with source='ollama' and honest score."""
    gateway = AIGateway()
    mock_niches = [
        {
            "name": "AI Productivity Tools",
            "description": "Short tutorials covering the best AI tools",
            "category": "Technology",
            "opportunity_score": 88,
            "target_audience": "Knowledge workers and tech enthusiasts",
            "suggested_pillars": ["AI Prompts", "Workflow Automation", "Tool Reviews"],
            "suggested_cadence_per_week": 4,
            "rationale": "High search volume for short-form automation tutorials",
            "source": "ollama",
            "confidence": 0.85
        },
        {
            "name": "Cybersecurity Tips for Beginners",
            "description": "Essential online privacy habits",
            "category": "Technology",
            "opportunity_score": 75,
            "target_audience": "General digital citizens",
            "suggested_pillars": ["Phishing Defense", "Password Security", "Privacy Tools"],
            "suggested_cadence_per_week": 3,
            "rationale": "Steady educational demand with high viewer retention",
            "source": "ollama",
            "confidence": 0.80
        }
    ]

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = f"```json\n{import_json(mock_niches)}\n```"
    mock_response.choices = [mock_choice]

    with patch.object(gateway.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        results = await gateway.generate_niche_recommendations({"name": "TechPulse", "description": "Latest tech trends"})
        
        assert len(results) == 2
        for r in results:
            assert isinstance(r, dict)
            validated = NicheRecommendation.model_validate(r)
            assert validated.source == "ollama"
            assert 0.0 <= validated.confidence <= 1.0
            assert 0 <= validated.opportunity_score <= 100
        assert results[0]["name"] == "AI Productivity Tools"


def import_json(data):
    import json
    return json.dumps(data)


@pytest.mark.asyncio
async def test_niche_recommendations_ollama_failure_fallback():
    """Verify graceful fallback to curated_heuristic when Ollama fails or times out."""
    gateway = AIGateway()

    with patch.object(gateway.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = Exception("Ollama connection failed or timed out")

        # Context has finance signals
        channel_context = {
            "name": "WealthHacks",
            "description": "Smart investing and budget tips for young adults"
        }
        results = await gateway.generate_niche_recommendations(channel_context)

        assert len(results) > 0
        for r in results:
            assert isinstance(r, dict)
            validated = NicheRecommendation.model_validate(r)
            assert validated.source == "curated_heuristic"
            assert 0.0 <= validated.confidence <= 1.0
            assert 0 <= validated.opportunity_score <= 100
            assert len(validated.suggested_pillars) >= 2


@pytest.mark.asyncio
async def test_niche_recommendations_json_repair():
    """Verify markdown wrapped, messy or unescaped JSON from LLM is repaired and parsed."""
    gateway = AIGateway()
    messy_content = """Here are the recommendations based on your channel:
```json
[
  {
    "name": "Stoic Wisdom Daily",
    "description": "Ancient Stoic philosophy for modern challenges",
    "category": "Philosophy",
    "opportunity_score": 82,
    "target_audience": "Self-improvement seekers",
    "suggested_pillars": ["Daily Meditations", "Mindset Shifts"],
    "suggested_cadence_per_week": 5,
    "rationale": "High quote-share virality on Shorts."
  }
]
```
Hope this helps!"""

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = messy_content
    mock_response.choices = [mock_choice]

    with patch.object(gateway.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        results = await gateway.generate_niche_recommendations({"name": "StoicMind"})

        assert len(results) == 1
        assert results[0]["name"] == "Stoic Wisdom Daily"
        assert results[0]["source"] == "ollama"


def test_niche_recommendations_context_awareness():
    """Verify heuristic recommendations adapt dynamically based on channel metadata."""
    gateway = AIGateway()
    
    # Tech channel context
    tech_niches = gateway._get_heuristic_niche_recommendations({
        "name": "DevForge",
        "description": "Python, Rust, and AI agents tutorials"
    })
    assert any("Code" in n["name"] or "Tech" in n["name"] or "Developer" in n["name"] for n in tech_niches)

    # History channel context
    history_niches = gateway._get_heuristic_niche_recommendations({
        "name": "Echoes of Rome",
        "description": "Ancient warfare and lost civilizations"
    })
    assert any("History" in n["name"] or "Ancient" in n["name"] or "War" in n["name"] for n in history_niches)


def test_autopilot_config_validation_valid():
    """Verify 8-step wizard schema validation accepts complete and valid configuration."""
    config_dict = {
        "mode": "full_autopilot",
        "format": "shorts",
        "niche": "Tech Breakdown",
        "custom_niche": None,
        "target_audience": "Software engineers and tech enthusiasts",
        "tone": "informative",
        "language": "en",
        "target_geography": "US",
        "content_pillars": ["AI Engineering", "Cloud Architecture", "System Design"],
        "schedule": {
            "frequency_per_week": 3,
            "timezone": "America/New_York",
            "days_of_week": [0, 2, 4],  # Mon, Wed, Fri
            "times": ["09:00", "18:00"]   # 2 slots/day * 3 days = 6 available slots
        },
        "approval_required": True,
        "privacy_status": "private"
    }

    config = AutopilotConfig.model_validate(config_dict)
    assert config.mode == AutopilotMode.full_autopilot
    assert config.format == ContentFormat.shorts
    assert config.schedule.frequency_per_week == 3
    assert config.schedule.timezone == "America/New_York"
    assert config.approval_required is True


@pytest.mark.asyncio
async def test_autopilot_config_invalid_frequency():
    """Verify frequency exceeding available day/time slots is rejected with a clear message."""
    mock_db = MagicMock()
    mock_db.channels = MagicMock()
    service = ChannelService(mock_db)

    # Mock finding channel
    service.channel_repo.find_by_id = AsyncMock(return_value={"_id": "chan_1", "user_id": "u1"})

    invalid_config = {
        "mode": "assisted",
        "format": "shorts",
        "niche": "Quick Facts",
        "schedule": {
            "frequency_per_week": 5,
            "timezone": "UTC",
            "days_of_week": [0],  # 1 day only
            "times": ["12:00"]    # 1 time slot only -> total 1 slot/week, but frequency is 5
        }
    }

    with pytest.raises(ValueError) as exc:
        await service.configure_autopilot("u1", "chan_1", invalid_config)
    assert "exceeds available schedule slots" in str(exc.value)


def test_autopilot_config_invalid_timezone():
    """Verify invalid IANA timezone fails validation."""
    with pytest.raises(ValidationError) as exc:
        PublishSchedule(
            frequency_per_week=2,
            timezone="Mars/Olympus_Mons",
            days_of_week=[0, 1],
            times=["12:00"]
        )
    assert "Invalid IANA timezone" in str(exc.value)


def test_autopilot_config_invalid_time_format():
    """Verify malformed 24h times fail validation."""
    with pytest.raises(ValidationError):
        PublishSchedule(
            frequency_per_week=1,
            timezone="UTC",
            days_of_week=[0],
            times=["25:00"]  # Invalid hour
        )

    with pytest.raises(ValidationError):
        PublishSchedule(
            frequency_per_week=1,
            timezone="UTC",
            days_of_week=[0],
            times=["9am"]  # Not HH:MM
        )


def test_timezone_conversion_slot_calculation():
    """Verify schedule times are properly interpreted in channel timezone and converted to UTC."""
    from datetime import datetime, timezone, timedelta

    tz_str = "Asia/Kolkata"  # UTC+5:30
    tz = zoneinfo.ZoneInfo(tz_str)
    
    # In Asia/Kolkata, 10:30 AM corresponds to 05:00 UTC
    local_dt = datetime(2026, 9, 15, 10, 30, tzinfo=tz)
    utc_dt = local_dt.astimezone(timezone.utc)

    assert utc_dt.hour == 5
    assert utc_dt.minute == 0
    assert utc_dt.tzinfo == timezone.utc

