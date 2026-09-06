from typing import Dict, List, Optional, Any
from loguru import logger
from backend.app.ai.gateway import AIGateway
from backend.app.repositories.content import ContentIdeaRepository, ScriptRepository
from backend.app.utils.serializers import serialize_doc, serialize_docs
from backend.app.models.content import StructuredScript

class ContentService:
    def __init__(self, db, ai_gateway: Optional[AIGateway] = None):
        self.idea_repo = ContentIdeaRepository(db)
        self.script_repo = ScriptRepository(db)
        self.ai = ai_gateway
    
    async def generate_ideas(self, user_id: str, channel_id: str, channel_context: dict) -> List[dict]:
        if not self.ai:
            raise ValueError("AI Gateway is not configured")
        ideas = await self.ai.generate_content_ideas(channel_context)
        created_ideas = []
        for idea in ideas:
            idea_doc = {
                "user_id": user_id,
                "channel_id": channel_id,
                "title": idea.get("title", "Untitled Idea"),
                "description": idea.get("description", ""),
                "keywords": idea.get("keywords", []),
                "target_audience": idea.get("target_audience", ""),
                "estimated_views": idea.get("estimated_views"),
                "status": "draft",
                "source": "ai_generated",
                "confidence": float(idea.get("confidence", 0.8))
            }
            idea_id = await self.idea_repo.insert_one(idea_doc)
            created_ideas.append(serialize_doc(idea_doc))
        return created_ideas
    
    async def list_ideas(self, user_id: str, channel_id: str, status: Optional[str] = None) -> List[dict]:
        ideas = await self.idea_repo.find_by_channel(user_id=user_id, channel_id=channel_id, status=status)
        return serialize_docs(ideas)
        
    async def get_idea(self, user_id: str, idea_id: str) -> Optional[dict]:
        idea = await self.idea_repo.find_by_id(idea_id, user_id=user_id)
        return serialize_doc(idea)
        
    async def update_idea_status(self, user_id: str, idea_id: str, status: str) -> bool:
        return await self.idea_repo.update_status(idea_id, user_id=user_id, status=status)
        
    async def create_idea(self, user_id: str, channel_id: str, data: dict) -> dict:
        data["user_id"] = user_id
        data["channel_id"] = channel_id
        data.setdefault("status", "draft")
        idea_id = await self.idea_repo.insert_one(data)
        data["id"] = idea_id
        return serialize_doc(data)
    
    async def generate_script(self, user_id: str, channel_id: str, topic: str, duration: int = 45, channel_context: Optional[dict] = None) -> dict:
        if not self.ai:
            raise ValueError("AI Gateway is not configured")
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty")
            
        try:
            # Generate full structured script containing multiple hooks, scoring, outline, script, CTA
            structured: StructuredScript = await self.ai.generate_structured_script(topic, channel_context=channel_context)
            final_script_text = structured.final_script.strip()
            title = structured.title.strip() or f"Script: {topic}"
            structured_payload = structured.model_dump()
        except Exception as e:
            logger.warning(f"Structured script generation fallback to standard generation: {e}")
            final_script_text = await self.ai.generate_script(topic, duration=duration)
            title = f"Script: {topic}"
            structured_payload = {"final_script": final_script_text}

        if not final_script_text:
            raise ValueError("AI returned an empty script. Video generation cannot proceed.")

        words = len(final_script_text.split())
        script_doc = {
            "user_id": user_id,
            "channel_id": channel_id,
            "title": title,
            "script_text": final_script_text,
            "duration_estimate": duration,
            "word_count": words,
            "version": 1,
            "status": "draft",
            "structured_data": structured_payload
        }
        script_id = await self.script_repo.insert_one(script_doc)
        return serialize_doc(script_doc)
    
    async def list_scripts(self, user_id: str, channel_id: str) -> List[dict]:
        scripts = await self.script_repo.find_by_channel(user_id=user_id, channel_id=channel_id)
        return serialize_docs(scripts)
        
    async def get_script(self, user_id: str, script_id: str) -> Optional[dict]:
        script = await self.script_repo.find_by_id(script_id, user_id=user_id)
        return serialize_doc(script)
        
    async def update_script(self, user_id: str, script_id: str, data: dict) -> bool:
        return await self.script_repo.update_one(script_id, data, user_id=user_id)

    async def create_script(self, user_id: str, channel_id: str, data: dict) -> dict:
        text = data.get("script_text", "")
        words = len(text.split()) if text else 0
        script_doc = {
            "user_id": user_id,
            "channel_id": channel_id,
            "title": data.get("title") or data.get("topic") or "Untitled Script",
            "script_text": text,
            "duration_estimate": data.get("duration_estimate") or data.get("duration", 45),
            "word_count": words,
            "version": 1,
            "status": data.get("status", "draft"),
            "content_idea_id": data.get("content_idea_id")
        }
        script_id = await self.script_repo.insert_one(script_doc)
        script_doc["id"] = script_id
        return serialize_doc(script_doc)