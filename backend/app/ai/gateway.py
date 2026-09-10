import json
import re
from typing import List, Dict, Any, Type, Optional
from pydantic import BaseModel, ValidationError
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError
from loguru import logger

from backend.app.ai.prompts import (
    SCRIPT_SYSTEM_PROMPT,
    SEARCH_TERMS_SYSTEM_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
    CONTENT_IDEAS_SYSTEM_PROMPT,
    PERFORMANCE_ANALYSIS_PROMPT,
    STRATEGY_INSIGHTS_PROMPT,
    CHANNEL_ONBOARDING_SYSTEM_PROMPT,
    OPPORTUNITY_FEED_PROMPT
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
    candidate = text
    match = re.search(r'```(?:json|python)?\s*([\s\S]*?)\s*```', text)
    if match:
        candidate = match.group(1).strip()
    
    # Try finding an object or array
    brace_match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', candidate)
    if brace_match:
        return brace_match.group(1).strip()
        
    return candidate.strip()

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
        
    async def _chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, response_format: Optional[dict] = None) -> str:
        """Raw chat completion with connection error interception."""
        try:
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature
            }
            if response_format:
                kwargs["response_format"] = response_format
                
            response = await self.client.chat.completions.create(**kwargs)
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
        
    async def _chat_json(self, system_prompt: str, user_prompt: str, response_model: Optional[Type[BaseModel]] = None, max_retries: int = 3) -> Any:
        """Structured JSON chat completion with syntax repair, Pydantic validation, and multi-turn retries."""
        enhanced_system_prompt = (
            f"{system_prompt}\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "- Return VALID JSON ONLY.\n"
            "- Do NOT wrap output in Python code blocks, functions, or markdown code blocks.\n"
            "- Do NOT include conversational commentary or preamble.\n"
            "- Output must begin with '{' or '[' and end with '}' or ']'."
        )
        
        last_error = None
        current_user_prompt = user_prompt
        
        for attempt in range(1, max_retries + 1):
            try:
                # Attempt structured JSON completion with response_format
                raw = await self._chat(
                    system_prompt=enhanced_system_prompt,
                    user_prompt=current_user_prompt,
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                
                json_str = repair_json_string(raw)
                try:
                    parsed = json.loads(json_str)
                except json.JSONDecodeError as decode_err:
                    logger.warning(f"JSON decode error (attempt {attempt}/{max_retries}): {decode_err}. Trying regex extraction...")
                    first_brace = raw.find("{")
                    last_brace = raw.rfind("}")
                    first_bracket = raw.find("[")
                    last_bracket = raw.rfind("]")
                    
                    # Pick whichever container starts earliest
                    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace) and last_bracket > first_bracket:
                        parsed = json.loads(raw[first_bracket:last_bracket+1])
                    elif first_brace != -1 and last_brace > first_brace:
                        parsed = json.loads(raw[first_brace:last_brace+1])
                    else:
                        raise decode_err
                        
                if response_model:
                    target_data = parsed
                    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                        target_data = parsed[0]
                    validated = response_model.model_validate(target_data)
                    return validated
                    
                return parsed
            except Exception as e:
                last_error = e
                logger.warning(f"Structured AI generation attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    # Provide targeted correction feedback for next turn
                    current_user_prompt = (
                        f"{user_prompt}\n\n"
                        f"[SYSTEM REPAIR NOTE]: Your previous output produced this error: {e}. "
                        "Please re-generate your response as valid, pure JSON matching the required schema exactly."
                    )
                    
        raise ValueError(f"STRUCTURED_GENERATION: FAIL - Exceeded {max_retries} retries. Final error: {last_error}")
        
    async def generate_script(self, topic: str, duration: int = 45, language: str = "en", paragraph_number: int = 1) -> str:
        """Generate a video script for the given topic."""
        prompt = f"Topic: {topic}\nDuration: {duration} seconds\nLanguage: {language}\nParagraphs: {paragraph_number}\nWrite a high-converting, engaging narration script. Return only the script text."
        script = await self._chat(SCRIPT_SYSTEM_PROMPT, prompt, temperature=0.7)
        return script.strip()

    async def generate_structured_script(self, topic: str, duration: int = 30, channel_context: Optional[dict] = None) -> StructuredScript:
        """Generate multiple hooks, evaluate them, outline, final script and CTA (Section 15)."""
        target_words = max(35, min(int(duration * 2.3), 85))
        prompt = f"""
Topic: {topic}
Target Duration: {duration} seconds (approximately {target_words} words for spoken narration)
Channel Context: {json.dumps(channel_context or {}, indent=2)}

Create a complete structured YouTube video script in valid JSON format:
{{
  "title": "Compelling Title",
  "hooks": ["Hook option 1", "Hook option 2", "Hook option 3"],
  "hook_scores": {{"Hook option 1": 8.5, "Hook option 2": 9.2, "Hook option 3": 7.8}},
  "selected_hook": "Hook option 2",
  "outline": ["Intro", "Core Insight", "Proof/Example", "Key Takeaway", "Call to Action"],
  "final_script": "A punchy {target_words}-word spoken voiceover script text...",
  "cta": "Subscribe for more insights and comment your thoughts below!"
}}

CRITICAL REQUIREMENT:
The "final_script" MUST be approximately {target_words} words long so that narration takes exactly ~{duration} seconds.
"""
        return await self._chat_json(SCRIPT_SYSTEM_PROMPT, prompt, response_model=StructuredScript)

    async def rewrite_structured_script(
        self,
        original_script: str,
        instruction: str,
        duration: int = 45,
        channel_context: Optional[dict] = None
    ) -> StructuredScript:
        """Rewrite a script based on specific instruction and channel rules."""
        target_words = int(duration * 2.5)
        prompt = f"""
ORIGINAL SCRIPT:
{original_script}

REWRITE INSTRUCTION:
{instruction}

CHANNEL CONTEXT & RULES:
{json.dumps(channel_context or {}, indent=2)}

TARGET DURATION: ~{duration} seconds (approx. {target_words} words).

Generate the revised script in StructuredScript JSON format with title, hooks, outline, final_script, and cta.
The 'final_script' MUST strictly be approximately {target_words} words long.
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
        return await self._chat_json(RESEARCH_SYSTEM_PROMPT, prompt, response_model=ResearchOpportunity)

    async def generate_opportunity_feed(self, channel_context: dict, count: int = 5) -> List[ResearchOpportunity]:
        """Generate high-yield opportunity feed directly grounded in Channel Brain."""
        prompt = f"""
Channel Context & Intelligence:
{json.dumps(channel_context, indent=2)}

Generate {count} unique, high-potential YouTube Shorts opportunities adhering strictly to the JSON array schema.
"""
        result = await self._chat_json(OPPORTUNITY_FEED_PROMPT, prompt)
        opportunities: List[ResearchOpportunity] = []
        if isinstance(result, list):
            for item in result:
                try:
                    opp = ResearchOpportunity.model_validate(item)
                    opportunities.append(opp)
                except Exception as e:
                    logger.warning(f"Skipping malformed opportunity: {e}")
        elif isinstance(result, dict) and "opportunities" in result:
            for item in result["opportunities"]:
                try:
                    opp = ResearchOpportunity.model_validate(item)
                    opportunities.append(opp)
                except Exception:
                    pass

        if not opportunities:
            niche = channel_context.get("niche", "Technology")
            pillars = channel_context.get("content_pillars", [])
            pillar_name = pillars[0].get("name") if pillars and isinstance(pillars[0], dict) else (pillars[0] if pillars else niche)
            opportunities.append(ResearchOpportunity(
                topic=f"The Truth About {niche} in 2026",
                content_pillar=pillar_name,
                target_audience=channel_context.get("target_audience", "Tech Enthusiasts"),
                why_now="Rapid evolution and viewer demand for concise breakdown",
                evidence="High search volume on YouTube Shorts",
                content_gap="Most videos are overly technical without visual demonstrations",
                recommended_angle="Show concrete proof within 30 seconds",
                hooks=[f"Stop scrolling if you think {niche} is what you think it is..."],
                sources=["Industry analysis 2026"],
                opportunity_score=88.5,
                confidence=0.85
            ))
        return opportunities[:count]


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
        
    async def generate_channel_brain_strategy(self, onboarding_data: dict) -> Dict[str, Any]:
        """Generate comprehensive channel brain strategy from onboarding parameters."""
        prompt = f"""
Channel Niche: {onboarding_data.get('niche')}
Target Audience: {onboarding_data.get('target_audience')}
Desired Tone: {onboarding_data.get('tone', 'engaging')}
Seed Content Pillars: {onboarding_data.get('content_pillars', [])}
Target Geography: {onboarding_data.get('target_geography', 'US')}
Language: {onboarding_data.get('language', 'en')}
Reference Channels: {onboarding_data.get('reference_channels', [])}
Custom Instructions: {onboarding_data.get('custom_instructions', '')}

Generate the complete strategic channel brain in JSON format according to the requested schema.
"""
        result = await self._chat_json(CHANNEL_ONBOARDING_SYSTEM_PROMPT, prompt)
        if not isinstance(result, dict):
            result = {}

        result.setdefault("positioning", f"The premier YouTube Shorts channel for {onboarding_data.get('niche')}.")
        pillars = onboarding_data.get("content_pillars") or [onboarding_data.get("niche")]
        result.setdefault("content_pillars", [
            {"name": p, "description": f"Dedicated insights covering {p}", "target_ratio": round(1.0 / len(pillars), 2)}
            for p in pillars
        ])
        result.setdefault("winning_hooks", [
            {"hook_type": "curiosity_gap", "pattern": "Most people think {myth}, but here is the truth...", "effectiveness_score": 0.85},
            {"hook_type": "shocking_fact", "pattern": "This {topic} fact will completely change how you see {benefit}...", "effectiveness_score": 0.8}
        ])
        result.setdefault("winning_title_patterns", [
            "Why {Subject} Is Not What You Think #Shorts",
            "3 {Subject} Secrets Nobody Tells You #Shorts"
        ])
        result.setdefault("best_publish_times", ["Tuesday 18:00 UTC", "Thursday 20:00 UTC", "Saturday 15:00 UTC"])
        result.setdefault("learned_rules", [
            "Start with visual motion in the first 1.5 seconds",
            "Deliver payoff before second 40"
        ])
        return result

    async def check_health(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
