import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from loguru import logger

class VisualScene(BaseModel):
    scene_index: int
    text: str
    duration: float = Field(default=3.5, ge=1.5, le=8.0)
    search_queries: List[str] = Field(default_factory=list)
    visual_intent: str = "b-roll"
    aspect_ratio: str = "9:16"

    @model_validator(mode="before")
    @classmethod
    def validate_scene(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Ensure queries are clean strings
            queries = data.get("search_queries") or data.get("queries") or []
            if isinstance(queries, str):
                queries = [q.strip() for q in queries.split(",") if q.strip()]
            data["search_queries"] = [str(q).strip() for q in queries if str(q).strip()]
            
            # Ensure text is not empty
            if not data.get("text"):
                data["text"] = data.get("narration") or "Visual transition"
        return data

class VisualStoryboard(BaseModel):
    title: str = ""
    total_duration: float = 0.0
    aspect_ratio: str = "9:16"
    scenes: List[VisualScene] = Field(default_factory=list)

    def total_scene_duration(self) -> float:
        return sum(s.duration for s in self.scenes)

# Curated stop words to clean up heuristic visual search queries
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "through", "about", "for", "is", "of", "while", "during",
    "to", "from", "in", "out", "on", "off", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "can", "will",
    "don't", "should", "now", "it's", "you're", "we're", "they're", "i'm"
}

class StoryboardGenerator:
    """Segments a video script into timed scenes (2.0s - 5.0s) with concrete visual search terms."""

    def __init__(self, ai_gateway=None):
        self.ai = ai_gateway

    async def generate_storyboard(
        self,
        script: str,
        total_duration: float = 0.0,
        topic: str = "",
        aspect_ratio: str = "9:16"
    ) -> VisualStoryboard:
        script = script.strip()
        if not script:
            raise ValueError("Cannot generate storyboard from empty script")

        words = script.split()
        word_count = len(words)
        
        # If total duration not provided, estimate at ~2.5 words per second (150 wpm)
        if total_duration <= 0.0:
            total_duration = max(word_count / 2.5, 5.0)

        # Attempt AI generation if gateway is present
        if self.ai:
            try:
                storyboard = await self._generate_ai_storyboard(
                    script=script,
                    total_duration=total_duration,
                    topic=topic,
                    aspect_ratio=aspect_ratio
                )
                if storyboard and len(storyboard.scenes) > 0:
                    return storyboard
            except Exception as e:
                logger.warning(f"AI storyboard generation failed ({e}), falling back to heuristic engine")

        # Heuristic rule-based segmentation fallback
        return self._generate_heuristic_storyboard(
            script=script,
            total_duration=total_duration,
            topic=topic,
            aspect_ratio=aspect_ratio
        )

    async def _generate_ai_storyboard(
        self,
        script: str,
        total_duration: float,
        topic: str,
        aspect_ratio: str
    ) -> Optional[VisualStoryboard]:
        system_prompt = (
            "You are an expert video director and storyboard artist for high-retention viral YouTube Shorts.\n"
            "Your task is to take a spoken script and break it down into sequential visual scenes.\n\n"
            "STRICT RULES:\n"
            "1. Each scene MUST be between 2.0 and 4.5 seconds in duration.\n"
            "2. Fast visual pacing is essential for retention (no scene longer than 5 seconds).\n"
            "3. The sum of scene durations must approximately equal the total script duration.\n"
            "4. For each scene, generate 3 to 4 concrete, tangible, photorealistic Pexels search queries.\n"
            "   - GOOD queries: 'programmer typing laptop neon lights', 'frustrated businesswoman head in hands', 'futuristic city drone shot vertical'\n"
            "   - BAD queries: 'concept of efficiency', 'revolution', 'abstract idea' (stock footage search will fail on abstract words).\n"
            "5. Format output STRICTLY as valid JSON matching this schema:\n"
            "{\n"
            '  "title": "...",\n'
            '  "scenes": [\n'
            '    {\n'
            '      "scene_index": 1,\n'
            '      "text": "spoken words for this scene",\n'
            '      "duration": 3.2,\n'
            '      "search_queries": ["concrete query 1", "concrete query 2", "concrete query 3"],\n'
            '      "visual_intent": "b-roll"\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        user_prompt = (
            f"Topic: {topic or 'YouTube Short'}\n"
            f"Target Total Duration: {total_duration:.1f} seconds\n"
            f"Aspect Ratio: {aspect_ratio}\n"
            f"Full Script:\n{script}"
        )

        result = await self.ai._chat_json(system_prompt, user_prompt)
        if not isinstance(result, dict) or "scenes" not in result:
            return None

        scenes_data = result.get("scenes", [])
        scenes: List[VisualScene] = []
        for i, s in enumerate(scenes_data):
            text = s.get("text", "").strip() or f"Scene {i+1}"
            dur = float(s.get("duration", 3.0))
            dur = max(2.0, min(5.0, dur))  # Enforce [2.0, 5.0] constraint
            queries = s.get("search_queries") or [topic or "cinematic b-roll"]
            intent = s.get("visual_intent", "b-roll")
            scenes.append(VisualScene(
                scene_index=i + 1,
                text=text,
                duration=dur,
                search_queries=queries,
                visual_intent=intent,
                aspect_ratio=aspect_ratio
            ))

        if not scenes:
            return None

        return VisualStoryboard(
            title=result.get("title", topic or "Visual Storyboard"),
            total_duration=sum(s.duration for s in scenes),
            aspect_ratio=aspect_ratio,
            scenes=scenes
        )

    def _generate_heuristic_storyboard(
        self,
        script: str,
        total_duration: float,
        topic: str,
        aspect_ratio: str
    ) -> VisualStoryboard:
        """Splits script into sentences/clauses and maps to 2.5s-4.0s scenes with concrete visual keywords."""
        # Split script by sentence boundaries or punctuation pauses
        raw_chunks = [c.strip() for c in re.split(r'(?<=[.?!;:,])\s+', script) if c.strip()]
        if not raw_chunks:
            raw_chunks = [script]

        # Consolidate chunks so each is roughly 5 to 14 words (~2 to 5 seconds)
        balanced_chunks: List[str] = []
        current_chunk: List[str] = []
        current_words = 0

        for chunk in raw_chunks:
            c_words = len(chunk.split())
            if current_words + c_words > 14 and current_chunk:
                balanced_chunks.append(" ".join(current_chunk))
                current_chunk = [chunk]
                current_words = c_words
            else:
                current_chunk.append(chunk)
                current_words += c_words

        if current_chunk:
            balanced_chunks.append(" ".join(current_chunk))

        total_words = max(len(script.split()), 1)
        scenes: List[VisualScene] = []

        topic_clean = re.sub(r'[^a-zA-Z0-9\s]', '', topic).lower().strip()
        topic_words = [w for w in topic_clean.split() if w not in STOP_WORDS]
        topic_fallback = " ".join(topic_words[:3]) if topic_words else "cinematic vertical"

        for idx, text in enumerate(balanced_chunks):
            chunk_word_count = len(text.split())
            # Duration proportional to word count
            proportional_dur = (chunk_word_count / total_words) * total_duration
            dur = round(max(2.0, min(5.0, proportional_dur)), 1)

            # Extract visual keywords from chunk
            clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', text).lower()
            meaningful_words = [w for w in clean_text.split() if w not in STOP_WORDS and len(w) > 2]

            queries = []
            if len(meaningful_words) >= 2:
                queries.append(f"{' '.join(meaningful_words[:3])} {topic_fallback}".strip())
                queries.append(" ".join(meaningful_words[:2]))
            elif len(meaningful_words) == 1:
                queries.append(f"{meaningful_words[0]} {topic_fallback}".strip())
            
            queries.append(f"{topic_fallback} 4k vertical")
            queries.append("cinematic dynamic motion")

            scenes.append(VisualScene(
                scene_index=idx + 1,
                text=text,
                duration=dur,
                search_queries=queries[:3],
                visual_intent="b-roll" if idx > 0 else "hook",
                aspect_ratio=aspect_ratio
            ))

        return VisualStoryboard(
            title=topic or "Auto Storyboard",
            total_duration=sum(s.duration for s in scenes),
            aspect_ratio=aspect_ratio,
            scenes=scenes
        )
