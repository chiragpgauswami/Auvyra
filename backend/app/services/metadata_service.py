import re
from typing import Optional, Dict, Any, List
from loguru import logger
from backend.app.models.metadata import VideoMetadataPackage
from backend.app.ai.gateway import AIGateway

class MetadataService:
    """Generates high-CTR, SEO-optimized YouTube titles, descriptions, tags, and thumbnail concepts."""

    def __init__(self, ai_gateway: Optional[AIGateway] = None):
        self.ai = ai_gateway

    async def generate_metadata(
        self,
        topic: str,
        script: str = "",
        channel_context: Optional[Dict[str, Any]] = None
    ) -> VideoMetadataPackage:
        topic = topic.strip()
        if not topic and not script:
            raise ValueError("Cannot generate metadata without topic or script")

        channel_niche = (channel_context or {}).get("niche", "General")
        winning_hooks = (channel_context or {}).get("winning_hooks", [])

        if self.ai:
            try:
                system_prompt = (
                    "You are an elite YouTube growth strategist and SEO specialist.\n"
                    "Generate a high-converting metadata package for a YouTube Short / video.\n\n"
                    "CRITICAL CONSTRAINTS:\n"
                    "1. 'title': Must be under 75 characters, high curiosity/urgency, no clickbait lying.\n"
                    "2. 'title_candidates': Provide 3 alternative title angles.\n"
                    "3. 'description': Engaging 3-4 sentence breakdown + call to subscribe + 3 hashtags.\n"
                    "4. 'tags': 10-15 relevant SEO tags (comma-separated concept words).\n"
                    "5. 'hashtags': 3-5 relevant hashtags starting with #.\n"
                    "6. 'thumbnail_text_overlay': 2-4 BOLD, punchy words for the thumbnail graphic (e.g. 'DO THIS FIRST', 'IT'S OVER?').\n"
                    "7. Return STRICTLY valid JSON matching the schema."
                )

                user_prompt = (
                    f"Topic: {topic}\n"
                    f"Niche: {channel_niche}\n"
                    f"Sample Winning Hooks: {winning_hooks}\n"
                    f"Narration Script:\n{script[:1500]}"
                )

                result = await self.ai._chat_json(system_prompt, user_prompt)
                if isinstance(result, dict) and "title" in result:
                    return VideoMetadataPackage.model_validate(result)
            except Exception as e:
                logger.warning(f"AI metadata generation failed: {e}. Falling back to rule-based generator.")

        return self._generate_heuristic_metadata(topic, script, channel_niche)

    def _generate_heuristic_metadata(
        self,
        topic: str,
        script: str,
        channel_niche: str
    ) -> VideoMetadataPackage:
        clean_topic = re.sub(r'[^a-zA-Z0-9\s]', '', topic).strip() or "Must Watch"
        words = clean_topic.split()

        # Generate primary title and variations
        main_title = f"{clean_topic.title()} (Shocking Truth)"[:75]
        candidates = [
            f"The Secret to {clean_topic.title()}"[:75],
            f"Stop Doing {clean_topic.title()} Wrong"[:75],
            f"Why {clean_topic.title()} Changes Everything"[:75]
        ]

        # Extract keywords for tags
        clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', f"{topic} {script}").lower()
        unique_words = list(dict.fromkeys([w for w in clean_text.split() if len(w) > 3]))
        tags = unique_words[:12]
        if channel_niche.lower() not in tags:
            tags.insert(0, channel_niche.lower())

        hashtags = [f"#{channel_niche.replace(' ', '')}", "#shorts", "#trending"]
        if words:
            hashtags.insert(0, f"#{words[0].capitalize()}")

        description = (
            f"{clean_topic.title()}.\n\n"
            f"In this video, we break down what you need to know about {topic.lower()}. "
            "Subscribe for more daily breakdowns and actionable insights!\n\n"
            f"{' '.join(hashtags)}"
        )

        thumbnail_overlay = " ".join(words[:3]).upper() if words else "MUST WATCH"

        return VideoMetadataPackage(
            title=main_title,
            title_candidates=candidates,
            description=description,
            tags=tags,
            hashtags=hashtags,
            thumbnail_concept="High contrast subject with bold question mark",
            thumbnail_text_overlay=thumbnail_overlay[:30]
        )
