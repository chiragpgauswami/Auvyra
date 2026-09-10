import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.video.storyboard import StoryboardGenerator, VisualScene, VisualStoryboard

def test_visual_scene_model():
    scene = VisualScene(
        scene_index=1,
        text="Stop scrolling right now if you build software.",
        duration=3.2,
        search_queries=["developer surprised phone screen", "programmer late night code"],
        visual_intent="hook"
    )
    assert scene.scene_index == 1
    assert scene.duration == 3.2
    assert len(scene.search_queries) == 2
    assert scene.visual_intent == "hook"

def test_heuristic_storyboard_segmentation():
    script = (
        "Stop scrolling right now if you build software. "
        "Here are three AI tools that will literally save you twenty hours of coding every single week. "
        "First, automated bug diagnosis finds null pointers instantly. "
        "Second, neural test generators write all your edge cases. "
        "And third, auto-refactoring keeps your architecture clean. "
        "Subscribe for more high-leverage developer breakdowns."
    )
    generator = StoryboardGenerator()
    storyboard = generator._generate_heuristic_storyboard(
        script=script,
        total_duration=30.0,
        topic="AI Developer Tools",
        aspect_ratio="9:16"
    )

    assert isinstance(storyboard, VisualStoryboard)
    assert len(storyboard.scenes) >= 4

    for scene in storyboard.scenes:
        # Every scene must satisfy duration bounds
        assert 2.0 <= scene.duration <= 5.0
        # Every scene must have valid search queries
        assert len(scene.search_queries) >= 1
        for q in scene.search_queries:
            assert len(q.strip()) > 0

@pytest.mark.asyncio
async def test_ai_storyboard_generation():
    mock_ai = MagicMock()
    mock_ai._chat_json = AsyncMock(return_value={
        "title": "5 Coding Secrets",
        "scenes": [
            {
                "scene_index": 1,
                "text": "Stop coding like it's 2015.",
                "duration": 3.0,
                "search_queries": ["frustrated software developer", "monochrome computer terminal"],
                "visual_intent": "hook"
            },
            {
                "scene_index": 2,
                "text": "Modern AI pipelines do 80% of the repetitive scaffolding.",
                "duration": 4.2,
                "search_queries": ["matrix data stream futuristic", "cyberpunk server room rack"],
                "visual_intent": "b-roll"
            },
            {
                "scene_index": 3,
                "text": "Check the description link to try it today.",
                "duration": 2.5,
                "search_queries": ["hand holding smartphone vertical", "youtube subscribe button click"],
                "visual_intent": "cta"
            }
        ]
    })

    generator = StoryboardGenerator(ai_gateway=mock_ai)
    storyboard = await generator.generate_storyboard(
        script="Stop coding like it's 2015. Modern AI pipelines do 80% of the repetitive scaffolding. Check the description link to try it today.",
        total_duration=10.0,
        topic="Modern Coding",
        aspect_ratio="9:16"
    )

    assert storyboard.title == "5 Coding Secrets"
    assert len(storyboard.scenes) == 3
    assert storyboard.scenes[0].visual_intent == "hook"
    assert "frustrated software developer" in storyboard.scenes[0].search_queries
    assert storyboard.total_duration == pytest.approx(9.7, 0.1)
