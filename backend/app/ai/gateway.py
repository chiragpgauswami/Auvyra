import json
import re
from typing import List, Dict, Any, Type, Optional
from pydantic import BaseModel, ValidationError
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError
from loguru import logger

from backend.app.ai.prompts import (
    SCRIPT_SYSTEM_PROMPT,
    SEARCH_TERMS_SYSTEM_PROMPT,
    CONTENT_IDEAS_SYSTEM_PROMPT,
    PERFORMANCE_ANALYSIS_PROMPT,
    STRATEGY_INSIGHTS_PROMPT
)
from backend.app.models.content import StructuredScript, ResearchOpportunity

class OllamaUnavailableError(Exception):
    def __init__(self, message: str = "Ollama is unavailable. Ensure Ollama is running.", url: str = ""):
        super().__init__(message)
        self.code = "OLLAMA_UNAVAILABLE"
        self.message = message
        self.url = url

def extract_json(text: str) -> str:
    """Extract JSON string from text, repairing markdown codeblocks and outer text."""
    # Find ```json ... ``` blocks
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        return match.group(1).strip()
    
    # Try finding an object or array if no markdown blocks
    match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text)
    if match:
        return match.group(1).strip()
        
    return text.strip()

def repair_json_string(text: str) -> str:
    """Best-effort cleanup of common LLM JSON syntax issues."""
    cleaned = extract_json(text)
    # Remove trailing commas before closing braces/brackets
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    return cleaned

class AIGateway:
    """AI Gateway wrapping Ollama with structured output and Pydantic validation."""
    
    def __init__(self, base_url: Any = "http://localhost:11434", model: str = "llama3.1:8b"):
        if hasattr(base_url, "OLLAMA_BASE_URL"):
            settings_obj = base_url
            clean_url = str(settings_obj.OLLAMA_BASE_URL).rstrip("/")
            model_name = str(settings_obj.OLLAMA_MODEL)
        else:
            clean_url = str(base_url).rstrip("/")
            model_name = model
            
        self.base_url = clean_url
        self.client = AsyncOpenAI(
            base_url=f"{clean_url}/v1",
            api_key="ollama",
            timeout=30.0
        )
        self.model = model_name
        
    async def _chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """Raw chat completion with connection error interception."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature
            )
            return response.choices[0].message.content or ""
        except (APIConnectionError, APITimeoutError, ConnectionError) as e:
            logger.warning(f"Ollama connection error at {self.base_url}: {e}")
            raise OllamaUnavailableError(
                message=f"Ollama is unavailable at {self.base_url}. Please ensure Ollama is running and model '{self.model}' is installed.",
                url=self.base_url
            ) from e
        except Exception as e:
            logger.error(f"AI chat request failed: {e}")
            raise
        
    async def _chat_json(self, system_prompt: str, user_prompt: str, response_model: Optional[Type[BaseModel]] = None) -> Any:
        """Chat with JSON output extraction, syntax repair, and optional Pydantic validation."""
        raw = await self._chat(system_prompt, user_prompt, temperature=0.3)
        json_str = repair_json_string(raw)
        
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}. Attempting second repair pass on: {raw[:200]}")
            # Try aggressive search between first { and last }
            first_brace = raw.find("{")
            last_brace = raw.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                try:
                    parsed = json.loads(raw[first_brace:last_brace+1])
                except Exception:
                    raise ValueError(f"Failed to parse valid JSON from AI response: {raw}")
            else:
                raise ValueError(f"Failed to parse valid JSON from AI response: {raw}")
            
        if response_model:
            try:
                validated = response_model.model_validate(parsed)
                return validated
            except ValidationError as ve:
                logger.error(f"Pydantic validation failed on AI output: {ve}")
                raise ValueError(f"AI response failed schema validation: {ve}")
                
        return parsed
        
    async def generate_script(self, topic: str, duration: int = 45, language: str = "en", paragraph_number: int = 1) -> str:
        """Generate a video script for the given topic."""
        prompt = f"Topic: {topic}\nDuration: {duration} seconds\nLanguage: {language}\nParagraphs: {paragraph_number}\nWrite a high-converting, engaging narration script. Return only the script text."
        script = await self._chat(SCRIPT_SYSTEM_PROMPT, prompt, temperature=0.7)
        return script.strip()

    async def generate_structured_script(self, topic: str, channel_context: Optional[dict] = None) -> StructuredScript:
        """Generate multiple hooks, evaluate them, outline, final script and CTA (Section 15)."""
        prompt = f"""
Topic: {topic}
Channel Context: {json.dumps(channel_context or {}, indent=2)}

Create a complete structured YouTube video script in valid JSON format:
{{
  "title": "Compelling Title",
  "hooks": ["Hook option 1", "Hook option 2", "Hook option 3"],
  "hook_scores": {{"Hook option 1": 8.5, "Hook option 2": 9.2, "Hook option 3": 7.8}},
  "selected_hook": "Hook option 2",
  "outline": ["Intro", "Core Insight", "Proof/Example", "Key Takeaway", "Call to Action"],
  "final_script": "The full voiceover script text...",
  "cta": "Subscribe for more insights and comment your thoughts below!"
}}
"""
        return await self._chat_json(SCRIPT_SYSTEM_PROMPT, prompt, response_model=StructuredScript)

    async def generate_research_opportunity(self, topic: str, channel_context: Optional[dict] = None) -> ResearchOpportunity:
        """Generate opportunity research containing topic, why_now, evidence, content_gap, hooks, sources, confidence (Section 14)."""
        prompt = f"""
Topic: {topic}
Channel Context: {json.dumps(channel_context or {}, indent=2)}

Generate structured content opportunity research in valid JSON:
{{
  "topic": "{topic}",
  "why_now": "Why this topic is trending and timely right now",
  "evidence": "Data points or audience interest signals",
  "content_gap": "What other creators are missing on this topic",
  "recommended_angle": "The unique angle to take for maximum engagement",
  "hooks": ["Opening hook 1", "Opening hook 2"],
  "sources": ["Industry reports", "Audience questions"],
  "confidence": 0.85
}}
"""
        return await self._chat_json(CONTENT_IDEAS_SYSTEM_PROMPT, prompt, response_model=ResearchOpportunity)

    async def generate_search_terms(self, script: str, amount: int = 5) -> List[str]:
        """Generate visual search terms from a script."""
        prompt = f"Script:\n{script}\n\nExtract {amount} visual search terms as a JSON array of strings: [\"term1\", \"term2\", ...]"
        result = await self._chat_json(SEARCH_TERMS_SYSTEM_PROMPT, prompt)
        if isinstance(result, list):
            return [str(t) for t in result]
        if isinstance(result, dict) and "terms" in result:
            return [str(t) for t in result["terms"]]
        return [word for word in script.split() if len(word) > 4][:amount]
        
    async def generate_content_ideas(self, channel_context: dict, count: int = 5) -> List[Dict[str, Any]]:
        """Generate content ideas based on channel context."""
        prompt = f"Channel Context:\n{json.dumps(channel_context, indent=2)}\n\nGenerate {count} ideas as a JSON array of objects with title, description, keywords, target_audience."
        result = await self._chat_json(CONTENT_IDEAS_SYSTEM_PROMPT, prompt)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "ideas" in result:
            return result["ideas"]
        return []
        
    async def analyze_performance(self, analytics_data: dict) -> Dict[str, Any]:
        """Analyze video/channel performance data."""
        prompt = f"Analytics Data:\n{json.dumps(analytics_data, indent=2)}"
        return await self._chat_json(PERFORMANCE_ANALYSIS_PROMPT, prompt)
        
    async def generate_strategy_insights(self, channel_memory: dict, analytics: dict) -> List[Dict[str, Any]]:
        """Generate strategic insights for a channel."""
        prompt = f"Channel Memory:\n{json.dumps(channel_memory, indent=2)}\n\nAnalytics:\n{json.dumps(analytics, indent=2)}"
        result = await self._chat_json(STRATEGY_INSIGHTS_PROMPT, prompt)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "insights" in result:
            return result["insights"]
        return []
        
    async def check_health(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
