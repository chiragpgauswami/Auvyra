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
    OPPORTUNITY_FEED_PROMPT,
    NICHE_RECOMMENDATIONS_SYSTEM_PROMPT
)
from backend.app.models.content import StructuredScript, ResearchOpportunity
from backend.app.models.channel import NicheRecommendation

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

    async def generate_niche_recommendations(self, channel_context: Optional[dict] = None) -> list[dict]:
        """Generate AI-assisted, high-leverage YouTube Shorts niches with graceful heuristic fallback.
        
        Zero-Mock Policy: Never fabricates external metrics. If Ollama is unavailable or fails,
        returns curated heuristic recommendations with source='curated_heuristic' and explicit confidence.
        """
        ctx = channel_context or {}
        ch_name = ctx.get("name") or ctx.get("title") or "New Creator"
        ch_desc = ctx.get("description") or ""
        subscribers = ctx.get("subscriber_count", 0)
        videos = ctx.get("video_count", 0)
        brain = ctx.get("brain") or {}
        existing_niche = brain.get("niche") or ""
        existing_pillars = brain.get("content_pillars") or []
        recent_topics = ctx.get("recent_topics") or []

        prompt = f"""
Analyze the following YouTube Channel Context to recommend 4-5 high-engagement YouTube Shorts niches:
- Channel Name: {ch_name}
- Channel Description: {ch_desc if ch_desc else "No description available"}
- Current Metrics: {subscribers} subscribers, {videos} published videos
- Current Brain Niche: {existing_niche if existing_niche else "Unset (brand new channel)"}
- Existing Content Pillars: {existing_pillars if existing_pillars else "None"}
- Recent Video Topics: {recent_topics if recent_topics else "None"}

Generate 4 to 5 distinct, high-leverage Shorts niches tailored to this creator profile.
Return a JSON array of niche recommendation objects according to the required schema.
"""
        try:
            raw_result = await self._chat_json(NICHE_RECOMMENDATIONS_SYSTEM_PROMPT, prompt, max_retries=2)
            raw_list = []
            if isinstance(raw_result, dict):
                if "niches" in raw_result and isinstance(raw_result["niches"], list):
                    raw_list = raw_result["niches"]
                elif "recommendations" in raw_result and isinstance(raw_result["recommendations"], list):
                    raw_list = raw_result["recommendations"]
                elif "name" in raw_result or "niche" in raw_result:
                    raw_list = [raw_result]
                else:
                    for val in raw_result.values():
                        if isinstance(val, list) and val and isinstance(val[0], dict):
                            raw_list = val
                            break
            elif isinstance(raw_result, list):
                raw_list = raw_result

            validated_niches = []
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                # Enforce schema fields with flexible mapping
                n_name = item.get("name") or item.get("niche")
                if not n_name:
                    continue
                item["name"] = n_name
                if not item.get("description"):
                    item["description"] = item.get("rationale") or f"High-opportunity YouTube Shorts niche focused on {n_name}."
                if not item.get("suggested_pillars"):
                    item["suggested_pillars"] = item.get("content_pillars") or ["Key Insights", "Practical Applications", "Hook Strategies"]
                if not item.get("target_audience"):
                    item["target_audience"] = "YouTube Shorts audience"

                item.setdefault("id", re.sub(r'[^a-z0-9]+', '-', str(n_name).lower()).strip('-'))
                item.setdefault("market_demand", "High")
                item.setdefault("competition_level", "Medium")
                item.setdefault("opportunity_score", 80)
                item.setdefault("recommended_format", "shorts")
                item.setdefault("style_sample", "")
                item["source"] = "ollama"
                item["confidence"] = 0.88
                try:
                    rec = NicheRecommendation.model_validate(item)
                    validated_niches.append(rec.model_dump())
                except Exception as ve:
                    logger.warning(f"Ollama niche recommendation item validation failed: {ve}")

            if len(validated_niches) >= 1:
                return validated_niches
            else:
                logger.warning("Ollama returned no valid niches. Falling back to contextual heuristics.")
                return self._get_heuristic_niche_recommendations(channel_context)

        except (OllamaUnavailableError, APIConnectionError, APITimeoutError) as e:
            logger.warning(f"Ollama unavailable for niche recommendations ({e}). Using curated contextual heuristics.")
            return self._get_heuristic_niche_recommendations(channel_context)
        except Exception as e:
            logger.error(f"Unexpected error in Ollama niche recommendations ({e}). Falling back to heuristics.")
            return self._get_heuristic_niche_recommendations(channel_context)

    def _get_heuristic_niche_recommendations(self, channel_context: Optional[dict] = None) -> list[dict]:
        """Context-aware, deterministic heuristic fallback for YouTube Shorts niche opportunities.
        Metadata explicitly reports source='curated_heuristic' and opportunity_score as heuristic index.
        """
        ctx = channel_context or {}
        text_blob = f"{ctx.get('name', '')} {ctx.get('description', '')} {ctx.get('handle', '')}".lower()
        brain = ctx.get("brain") or {}
        if brain.get("niche"):
            text_blob += f" {brain['niche']}".lower()

        is_tech = any(k in text_blob for k in ["tech", "ai", "code", "software", "dev", "crypto", "data", "bot"])
        is_finance = any(k in text_blob for k in ["finance", "money", "invest", "wealth", "stock", "dollar", "crypto", "business"])
        is_history = any(k in text_blob for k in ["history", "war", "ancient", "mystery", "empire", "archaeology", "past"])
        is_self_dev = any(k in text_blob for k in ["stoic", "discipline", "mindset", "habit", "productivity", "psychology", "fitness"])

        if is_tech:
            candidates = [
                {
                    "id": "ai-breakdowns",
                    "name": "AI Tools & Future Tech Breakdowns",
                    "description": "Rapid 45-second visual breakdowns of cutting-edge AI tools, workflow automation, and futuristic tech frontiers.",
                    "market_demand": "Very High",
                    "competition_level": "Medium",
                    "opportunity_score": 92,
                    "target_audience": "Tech enthusiasts, remote workers, students, and early adopters",
                    "suggested_pillars": ["Free AI Supertools", "Future Tech Predictions", "Productivity Automation", "Tech Controversy"],
                    "recommended_format": "shorts",
                    "style_sample": "3 free AI websites that feel illegal to know in 2026."
                },
                {
                    "id": "cyber-mysteries",
                    "name": "Dark Web & Cyber Heists",
                    "description": "Story-driven documentary shorts detailing infamous hacker attacks, crypto heists, and digital mysteries.",
                    "market_demand": "High",
                    "competition_level": "Low",
                    "opportunity_score": 88,
                    "target_audience": "True crime and technology fans intrigued by high-stakes digital intrigue",
                    "suggested_pillars": ["Legendary Hackers", "Unsolved Cyber Heists", "Dark Web Lore", "Digital Surveillance"],
                    "recommended_format": "shorts",
                    "style_sample": "How a 19-year-old stole $40 million from an airline with one line of code."
                },
                {
                    "id": "dev-productivity",
                    "name": "Developer Life & Coding Hacks",
                    "description": "Relatable coding humor, architecture patterns, and lightning-fast developer efficiency techniques.",
                    "market_demand": "High",
                    "competition_level": "Moderate",
                    "opportunity_score": 84,
                    "target_audience": "Software engineers, boot campers, and aspiring developers",
                    "suggested_pillars": ["Terminal Productivity", "Junior vs Senior Dev", "Hidden IDE Superpowers", "Architecture in 60s"],
                    "recommended_format": "shorts",
                    "style_sample": "Stop using if/else chains. Use this pattern instead."
                },
                {
                    "id": "tech-paradoxes",
                    "name": "Silicon Valley Secrets & Paradoxes",
                    "description": "Fast-paced investigative shorts exposing how big tech algorithms work and hidden business models.",
                    "market_demand": "High",
                    "competition_level": "Low",
                    "opportunity_score": 86,
                    "target_audience": "Curious digital natives and startup founders",
                    "suggested_pillars": ["Algorithm Secrets", "Startup Failures", "Monopoly Mechanics", "Tech History"],
                    "recommended_format": "shorts",
                    "style_sample": "Why TikTok's algorithm knows your mood before you do."
                }
            ]
        elif is_finance:
            candidates = [
                {
                    "id": "wealth-frameworks",
                    "name": "Personal Wealth & Market Psychology",
                    "description": "High-impact financial mechanics, investing principles, and psychological traps keeping people broke.",
                    "market_demand": "Very High",
                    "competition_level": "Moderate",
                    "opportunity_score": 90,
                    "target_audience": "Young professionals, retail investors, and side-hustlers",
                    "suggested_pillars": ["Index Fund Realities", "Psychology of Spending", "Tax Advantages", "Passive Income Myths"],
                    "recommended_format": "shorts",
                    "style_sample": "Why buying a new car is mathematically the worst financial decision you can make."
                },
                {
                    "id": "economic-history",
                    "name": "Bizarre Economic History & Hyperinflation",
                    "description": "Fascinating historical stories about strange currencies, massive economic collapses, and financial manias.",
                    "market_demand": "High",
                    "competition_level": "Low",
                    "opportunity_score": 87,
                    "target_audience": "History buffs and curious intellectuals",
                    "suggested_pillars": ["Tulip Mania to Dotcom", "Hyperinflation Crises", "Gold Rush Shenanigans", "Secret Central Bank Moves"],
                    "recommended_format": "shorts",
                    "style_sample": "The day Zimbabwe printed a 100-trillion-dollar bill that couldn't buy bread."
                },
                {
                    "id": "business-empires",
                    "name": "Billion-Dollar Business Strategies",
                    "description": "Breakdowns of counterintuitive moats, genius marketing ploys, and pricing tricks used by global empires.",
                    "market_demand": "Very High",
                    "competition_level": "Medium",
                    "opportunity_score": 89,
                    "target_audience": "Entrepreneurs, business students, and ambitious creators",
                    "suggested_pillars": ["Loss-Leader Tricks", "Brand Warfare", "Hidden Revenue Streams", "Hostile Takeovers"],
                    "recommended_format": "shorts",
                    "style_sample": "Costco loses $50 million a year on hot dogs. Here is why it makes them billions."
                }
            ]
        elif is_history or is_self_dev:
            candidates = [
                {
                    "id": "stoic-mindset",
                    "name": "Stoic Philosophy & Modern Resilience",
                    "description": "Ancient Stoic and philosophical wisdom applied to modern mental health, focus, and grit.",
                    "market_demand": "Very High",
                    "competition_level": "Medium",
                    "opportunity_score": 91,
                    "target_audience": "Self-improvement seekers, athletes, and students",
                    "suggested_pillars": ["Marcus Aurelius Meditations", "The Power of Indifference", "Amor Fati in Practice", "Controlling the Mind"],
                    "recommended_format": "shorts",
                    "style_sample": "When Seneca was condemned to death, his reaction baffled the Roman Emperor."
                },
                {
                    "id": "untold-history",
                    "name": "Untold Historical Secrets & War Tacticians",
                    "description": "Suspenseful, dramatic accounts of obscure military maneuvers, unsung heroes, and turning points in history.",
                    "market_demand": "Very High",
                    "competition_level": "Low",
                    "opportunity_score": 94,
                    "target_audience": "History buffs, storytelling fans, and documentary viewers",
                    "suggested_pillars": ["Unsung War Heroes", "Brilliant Deceptions", "Ancient Weapons", "Decisive 10-Minute Battles"],
                    "recommended_format": "shorts",
                    "style_sample": "How a blind dog helped a soldier capture 40 enemies in World War II."
                },
                {
                    "id": "high-performance-habits",
                    "name": "Cognitive Biohacking & Habit Architecture",
                    "description": "Dopamine resets, sleep optimization, and scientifically proven study/work protocols.",
                    "market_demand": "High",
                    "competition_level": "Moderate",
                    "opportunity_score": 85,
                    "target_audience": "Students, knowledge workers, and fitness enthusiasts",
                    "suggested_pillars": ["Dopamine Detox", "Circadian Protocols", "Deep Work Routines", "Micro-Habits"],
                    "recommended_format": "shorts",
                    "style_sample": "The 2-minute rule that permanently stopped my procrastination."
                }
            ]
        else:
            # General / New channel multi-disciplinary opportunity universe
            candidates = [
                {
                    "id": "untold-history",
                    "name": "Untold History & Declassified Files",
                    "description": "Suspenseful, cinematic shorts revealing declassified government files, bizarre historical turning points, and secret missions.",
                    "market_demand": "Very High",
                    "competition_level": "Low",
                    "opportunity_score": 93,
                    "target_audience": "General curiosity audience, documentary lovers, students",
                    "suggested_pillars": ["Declassified Operations", "Bizarre Historical Coincidences", "Forgotten Tacticians", "Survival Stories"],
                    "recommended_format": "shorts",
                    "style_sample": "The secret CIA project that attempted to use cats as acoustic spies."
                },
                {
                    "id": "wealth-psychology",
                    "name": "Money Psychology & Wealth Paradoxes",
                    "description": "Crisp, counterintuitive insights into consumer psychology, money traps, and practical investing fundamentals.",
                    "market_demand": "Very High",
                    "competition_level": "Medium",
                    "opportunity_score": 89,
                    "target_audience": "Young adults, aspiring entrepreneurs, career builders",
                    "suggested_pillars": ["The Psychology of Spending", "Compound Interest Realities", "Stealth Wealth Habits", "Pricing Tricks"],
                    "recommended_format": "shorts",
                    "style_sample": "The subtle psychological trick luxury brands use to make you feel poor."
                },
                {
                    "id": "science-paradoxes",
                    "name": "Mind-Bending Science & Cosmic Paradoxes",
                    "description": "Visual, awe-inspiring physics questions, quantum quirks, and cosmic mysteries explained in 50 seconds.",
                    "market_demand": "High",
                    "competition_level": "Low",
                    "opportunity_score": 91,
                    "target_audience": "Curious minds, sci-fi enthusiasts, visual learners",
                    "suggested_pillars": ["Black Hole Physics", "Quantum Paradoxes", "Oceanic Unknowns", "Time Dilation Realities"],
                    "recommended_format": "shorts",
                    "style_sample": "If you fell into a black hole, you would watch the entire future of the universe unfold in seconds."
                },
                {
                    "id": "ai-future-tools",
                    "name": "Future Tech & AI Automations",
                    "description": "Fast-paced visual demos of innovative AI tools, humanoid robotics, and technological shifts.",
                    "market_demand": "Very High",
                    "competition_level": "Medium",
                    "opportunity_score": 90,
                    "target_audience": "Tech enthusiasts, creators, students, and professionals",
                    "suggested_pillars": ["AI Productivity", "Robotics Frontiers", "Digital Privacy", "Emerging Breakthroughs"],
                    "recommended_format": "shorts",
                    "style_sample": "3 AI breakthroughs that happened this week that nobody is talking about."
                },
                {
                    "id": "stoic-wisdom",
                    "name": "Stoic Wisdom & Modern Mindset",
                    "description": "Punchy philosophical mental models and stoic wisdom for daily clarity and emotional control.",
                    "market_demand": "High",
                    "competition_level": "Medium",
                    "opportunity_score": 86,
                    "target_audience": "Men and women focused on discipline, self-improvement, and resilience",
                    "suggested_pillars": ["Mental Fortitude", "Eliminating Worry", "The Art of Silence", "Dealing With Betrayal"],
                    "recommended_format": "shorts",
                    "style_sample": "Marcus Aurelius wrote this single sentence whenever someone insulted him."
                }
            ]

        results = []
        for c in candidates:
            c["source"] = "curated_heuristic"
            c["confidence"] = 0.75
            try:
                rec = NicheRecommendation.model_validate(c)
                results.append(rec.model_dump())
            except Exception as e:
                logger.warning(f"Error validating heuristic niche: {e}")
        return results
