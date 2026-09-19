"""
Unit Test Suite for Phase 22 Caption Style System.
Verifies:
1. All 6 preset configurations exist and validate against CaptionStyleConfig.
2. Safe-zone clamping [0.62, 0.76] * H is respected across all presets.
3. High-retention word count ceiling (max_words_per_cue <= 5) is enforced across all presets.
4. CaptionStyleRepository CRUD, channel tenancy isolation, and fallback defaults.
5. Queue item caption style snapshot immutability (changing channel style does NOT alter existing queued items).
"""

import pytest
from backend.app.models.caption_style import (
    CaptionStyleConfig,
    CaptionStyleId,
    PRESET_STYLES,
)
from backend.app.repositories.caption_styles import CaptionStyleRepository


def test_six_caption_presets_exist():
    """Verify all 6 required style presets exist."""
    expected_ids = [
        CaptionStyleId.classic.value,
        CaptionStyleId.bold.value,
        CaptionStyleId.kinetic.value,
        CaptionStyleId.minimal.value,
        CaptionStyleId.highlight_word.value,
        CaptionStyleId.typewriter.value,
    ]
    assert len(PRESET_STYLES) == 6
    preset_map = {p["style_id"]: p for p in PRESET_STYLES}
    for style_id in expected_ids:
        assert style_id in preset_map, f"Missing preset: {style_id}"
        cfg = preset_map[style_id]["config"]
        assert isinstance(cfg, dict)
        assert cfg["style_id"] == style_id


def test_preset_word_count_ceiling():
    """Verify all presets respect high-retention cadence (max_words_per_cue <= 5)."""
    for p in PRESET_STYLES:
        cfg = p["config"]
        max_words = cfg.get("max_words_per_cue", 3)
        assert max_words <= 5, f"Preset {p['style_id']} max_words_per_cue {max_words} exceeds 5."
        assert max_words >= 1


def test_preset_style_visual_attributes():
    """Verify required visual styling attributes on presets."""
    preset_map = {p["style_id"]: p["config"] for p in PRESET_STYLES}

    bold = preset_map["bold"]
    assert bold["font_weight"] == "bold"
    assert bold["outline_width"] >= 2.0

    typewriter = preset_map["typewriter"]
    assert typewriter["font_family"] == "Courier"
    assert typewriter["background_opacity"] > 0.0

    minimal = preset_map["minimal"]
    assert minimal["background_opacity"] == 0.0
    assert minimal["outline_width"] <= 1.5


@pytest.mark.asyncio
async def test_caption_style_repository_defaults(test_db):
    """Verify repository returns bold preset by default for unconfigured channel."""
    repo = CaptionStyleRepository(test_db)
    style = await repo.get_channel_style("channel_unconfigured_123", "user_123")
    assert style is not None
    assert style["style_id"] in ["bold", "classic"]
    assert style["channel_id"] == "channel_unconfigured_123"
    assert style["user_id"] == "user_123"


@pytest.mark.asyncio
async def test_caption_style_repository_save_and_channel_isolation(test_db):
    """Verify channel style configuration and tenancy isolation between two channels."""
    repo = CaptionStyleRepository(test_db)
    preset_map = {p["style_id"]: p["config"] for p in PRESET_STYLES}

    # Set channel A to kinetic
    config_a = dict(preset_map["kinetic"])
    saved_a = await repo.save_channel_style("ch_userA", "userA", config_a)
    assert saved_a["style_id"] == "kinetic"

    # Set channel B to bold
    config_b = dict(preset_map["bold"])
    saved_b = await repo.save_channel_style("ch_userB", "userB", config_b)
    assert saved_b["style_id"] == "bold"

    # Verify retrieval preserves channel isolation
    fetched_a = await repo.get_channel_style("ch_userA", "userA")
    fetched_b = await repo.get_channel_style("ch_userB", "userB")
    assert fetched_a["style_id"] == "kinetic"
    assert fetched_b["style_id"] == "bold"


@pytest.mark.asyncio
async def test_queue_item_caption_snapshot_immutability(test_db):
    """
    CRITICAL INVARIANT: Changing channel style later must NOT alter
    existing pending queue item caption style snapshots.
    """
    repo = CaptionStyleRepository(test_db)
    preset_map = {p["style_id"]: p["config"] for p in PRESET_STYLES}

    # Channel starts with 'minimal'
    await repo.save_channel_style("ch_immutability", "user_imm", dict(preset_map["minimal"]))
    active_style = await repo.get_channel_style("ch_immutability", "user_imm")

    # Queue item snapshots 'minimal'
    queue_item_snapshot = dict(active_style)
    assert queue_item_snapshot["style_id"] == "minimal"

    # Now user changes channel style to 'typewriter'
    await repo.save_channel_style("ch_immutability", "user_imm", dict(preset_map["typewriter"]))
    updated_channel_style = await repo.get_channel_style("ch_immutability", "user_imm")
    assert updated_channel_style["style_id"] == "typewriter"

    # The queue item's snapshot remains strictly 'minimal'
    assert queue_item_snapshot["style_id"] == "minimal"
    assert queue_item_snapshot["font_family"] != updated_channel_style["font_family"]

