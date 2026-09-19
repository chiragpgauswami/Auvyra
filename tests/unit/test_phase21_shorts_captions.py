import pytest
from backend.app.video.subtitles.generator import group_words_into_shorts_cues, cues_to_srt

def test_empty_words_grouping():
    assert group_words_into_shorts_cues([]) == []

def test_word_grouping_normal_cadence():
    # 10 words at 0.3s intervals
    words = [
        {"word": f"word{i}", "start": i * 0.3, "end": (i + 1) * 0.3, "probability": 0.95}
        for i in range(10)
    ]
    cues = group_words_into_shorts_cues(words)
    assert len(cues) > 0
    for c in cues:
        assert c["word_count"] <= 5, f"Cue exceeded hard max 5 words: {c}"
        assert c["duration"] <= 1.4, f"Cue exceeded hard max 1.4s: {c}"
        assert c["start"] < c["end"]
        assert c["word_count"] >= 1

def test_punctuation_aware_boundary():
    words = [
        {"word": "Welcome", "start": 0.0, "end": 0.4},
        {"word": "to", "start": 0.4, "end": 0.6},
        {"word": "Auvyra.", "start": 0.6, "end": 1.0},  # terminal period!
        {"word": "The", "start": 1.05, "end": 1.3},
        {"word": "future", "start": 1.3, "end": 1.6},
        {"word": "starts", "start": 1.6, "end": 1.9},
        {"word": "now!", "start": 1.9, "end": 2.2},    # terminal exclamation!
    ]
    cues = group_words_into_shorts_cues(words)
    assert len(cues) >= 2
    # The first cue must end with "Auvyra."
    assert cues[0]["text"].endswith("Auvyra.")
    # The next cue must start with "The"
    assert cues[1]["text"].startswith("The")
    # All cues must respect word count ceiling
    for c in cues:
        assert c["word_count"] <= 5

def test_pause_aware_boundary():
    words = [
        {"word": "First", "start": 0.0, "end": 0.4},
        {"word": "part", "start": 0.4, "end": 0.8},
        # Big pause of 0.6s
        {"word": "second", "start": 1.4, "end": 1.8},
        {"word": "part", "start": 1.8, "end": 2.2},
    ]
    cues = group_words_into_shorts_cues(words)
    assert len(cues) == 2
    assert cues[0]["text"] == "First part"
    assert cues[1]["text"] == "second part"
    assert cues[0]["end"] <= 0.8
    assert cues[1]["start"] >= 0.8

def test_monotonic_timestamps():
    words = [
        {"word": "Quick", "start": 0.2, "end": 0.5},
        {"word": "brown", "start": 0.5, "end": 0.8},
        {"word": "fox", "start": 0.8, "end": 1.1},
        {"word": "jumps", "start": 1.1, "end": 1.4},
        {"word": "over", "start": 1.4, "end": 1.7},
        {"word": "lazy", "start": 1.7, "end": 2.0},
        {"word": "dog.", "start": 2.0, "end": 2.3},
    ]
    cues = group_words_into_shorts_cues(words)
    for i in range(1, len(cues)):
        assert cues[i]["start"] >= cues[i-1]["end"], f"Non-monotonic timestamps between cues {i-1} and {i}"

def test_cues_to_srt_formatting():
    cues = [
        {"index": 1, "start": 0.0, "end": 0.85, "text": "HELLO WORLD", "word_count": 2, "duration": 0.85},
        {"index": 2, "start": 0.85, "end": 1.7, "text": "SHORTS ON AUTOPILOT", "word_count": 3, "duration": 0.85},
    ]
    srt = cues_to_srt(cues)
    assert "1\n00:00:00,000 --> 00:00:00,850\nHELLO WORLD" in srt
    assert "2\n00:00:00,850 --> 00:00:01,700\nSHORTS ON AUTOPILOT" in srt

def test_safe_zone_positioning():
    from backend.app.video.composition.overlay import compute_safe_zone_position
    video_h = 1920
    # Test varying caption box heights
    for box_h in [40, 80, 120, 180, 240]:
        y_pos, top_r, bot_r = compute_safe_zone_position(box_h, video_h, 0.62, 0.76, 0.70)
        assert top_r >= 0.619, f"Top ratio {top_r} violated lower safe zone bound (0.62)"
        assert bot_r <= 0.761, f"Bottom ratio {bot_r} violated upper safe zone bound (0.76)"
        assert y_pos >= int(0.62 * video_h)
        assert (y_pos + box_h) <= int(0.76 * video_h) + 1

def test_resolve_platform_font():
    from backend.app.video.composition.overlay import resolve_platform_font
    font = resolve_platform_font()
    assert font is not None
    assert isinstance(font, str)
    assert len(font) > 0

def test_interval_union_calculation():
    from backend.app.video.composition.assembler import calculate_interval_union_coverage

    # Overlapping clips: (0, 5) and (3, 7) on 10s audio
    # Simple sum would be 5 + 4 = 9s.
    # True mathematical union is [0, 7] = 7s.
    intervals = [(0.0, 5.0), (3.0, 7.0)]
    union_dur, ratio = calculate_interval_union_coverage(intervals, total_duration=10.0)
    assert union_dur == 7.0
    assert ratio == 0.70

    # Disjoint clips: (0, 3) and (5, 8) on 10s audio -> 3 + 3 = 6s -> 0.60
    disjoint = [(0.0, 3.0), (5.0, 8.0)]
    u_dur2, ratio2 = calculate_interval_union_coverage(disjoint, total_duration=10.0)
    assert u_dur2 == 6.0
    assert ratio2 == 0.60

    # Completely duplicate/contained: (1, 4) and (1, 4) -> 3s
    dups = [(1.0, 4.0), (1.0, 4.0)]
    u_dur3, ratio3 = calculate_interval_union_coverage(dups, total_duration=10.0)
    assert u_dur3 == 3.0
    assert ratio3 == 0.30

def test_qa_rejects_insufficient_stock_coverage():
    from backend.app.autopilot.qa import QAEngine
    from backend.app.autopilot.exceptions import QAGateError

    # Passing stock_coverage_ratio = 0.50 (< 0.70 required) must trigger QAGateError
    with pytest.raises(QAGateError) as exc_info:
        QAEngine.inspect_and_gate(
            video_path="/tmp/nonexistent.mp4",
            stock_coverage_ratio=0.50
        )
    assert exc_info.value is not None

def test_qa_rejects_consecutive_duplicate_clips():
    from backend.app.autopilot.qa import QAEngine
    from backend.app.autopilot.exceptions import QAGateError

    # Identical clip repeated across all scenes
    scene_clips = ["/path/to/clip_a.mp4", "/path/to/clip_a.mp4", "/path/to/clip_a.mp4"]
    with pytest.raises(QAGateError):
        QAEngine.inspect_and_gate(
            video_path="/tmp/nonexistent.mp4",
            scene_clips=scene_clips
        )


