from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from loguru import logger

from backend.app.ai.gateway import AIGateway
from backend.app.repositories.channels import ChannelMemoryRepository, ChannelRepository
from backend.app.repositories.brain import ChannelBrainRepository
from backend.app.repositories.analytics import AnalyticsRepository
from backend.app.repositories.videos import VideoRepository
from backend.app.repositories.content import ScriptRepository
from backend.app.repositories.memory import AgentRunRepository
from backend.app.utils.serializers import serialize_doc

class LearningService:
    """Consumes analytics snapshots, analyzes performance trends, updates channel memory and ChannelBrain."""
    
    def __init__(self, db, ai_gateway: Optional[AIGateway] = None):
        self.channel_repo = ChannelRepository(db)
        self.memory_repo = ChannelMemoryRepository(db)
        self.brain_repo = ChannelBrainRepository(db)
        self.analytics_repo = AnalyticsRepository(db)
        self.video_repo = VideoRepository(db)
        self.script_repo = ScriptRepository(db)
        self.agent_run_repo = AgentRunRepository(db)
        self.ai = ai_gateway
    
    async def update_channel_memory(self, user_id: str, channel_id: str) -> dict:
        start_time = datetime.now(timezone.utc)
        
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or access denied")
            
        snapshots = await self.analytics_repo.find_by_channel(user_id, channel_id)
        memory = await self.memory_repo.get_memory(channel_id) or {
            "channel_id": channel_id,
            "best_topics": [],
            "weak_topics": [],
            "best_hooks": [],
            "best_video_lengths": [],
            "audience_insights": [],
            "strategy_insights": []
        }
        
        now = datetime.now(timezone.utc)
        derived_insights = []
        if self.ai:
            try:
                serialized_memory = serialize_doc(memory)
                serialized_snapshots = [serialize_doc(s) for s in snapshots]
                ai_insights = await self.ai.generate_strategy_insights(serialized_memory, {"snapshots": serialized_snapshots})
                if isinstance(ai_insights, list):
                    derived_insights.extend(ai_insights)
            except Exception as e:
                logger.warning(f"AI strategy generation fallback: {e}")
                
        if not derived_insights and snapshots:
            total_views = sum(s.get("views", 0) for s in snapshots)
            avg_ctr = sum(s.get("ctr", 0.0) for s in snapshots) / len(snapshots)
            derived_insights.append({
                "title": "Baseline Performance Evaluation",
                "description": f"Analyzed {len(snapshots)} snapshot(s) with {total_views} cumulative views and {avg_ctr:.2f}% avg CTR.",
                "source": "analytics_engine",
                "confidence": 0.9,
                "supporting_metrics": {"total_views": total_views, "sample_size": len(snapshots)},
                "created_at": now
            })

        best_topics = memory.get("best_topics", [])
        best_hooks = memory.get("best_hooks", [])

        for ins in derived_insights:
            if isinstance(ins, dict) and ins.get("insight_type") == "topic" and ins.get("title"):
                if not any(t.get("topic") == ins["title"] for t in best_topics):
                    best_topics.append({
                        "topic": ins["title"],
                        "confidence": ins.get("confidence", 0.8),
                        "updated_at": now
                    })

        memory["best_topics"] = best_topics
        memory["best_hooks"] = best_hooks
        memory.setdefault("strategy_insights", []).extend(derived_insights)
        memory["last_updated"] = now
        
        await self.memory_repo.update_memory(channel_id, memory)
        
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        await self.agent_run_repo.record_run(
            agent_type="learning_engine",
            user_id=user_id,
            channel_id=channel_id,
            input_data={"snapshots_count": len(snapshots)},
            output_data={"insights_generated": len(derived_insights)},
            duration_ms=duration_ms
        )
        
        return serialize_doc(memory)

    async def run_learning_cycle(self, user_id: str, channel_id: str) -> dict:
        """Executes full closed-loop feedback: updates channel memory and persists winning hooks/rules into ChannelBrain."""
        # 1. Update general channel memory
        memory = await self.update_channel_memory(user_id, channel_id)

        # 2. Extract top performing videos
        videos = await self.video_repo.find_by_channel(user_id=user_id, channel_id=channel_id)
        snapshots = await self.analytics_repo.find_by_channel(user_id=user_id, channel_id=channel_id)
        
        snap_map = {}
        for s in snapshots:
            vid_id = s.get("video_id")
            if vid_id:
                snap_map[vid_id] = s.get("views", 0)

        winning_hooks_added = 0
        rules_added = 0

        # Sort videos by views
        scored_videos = []
        for v in videos:
            v_id = str(v.get("_id"))
            score = snap_map.get(v_id, 0)
            scored_videos.append((score, v))

        scored_videos.sort(key=lambda x: x[0], reverse=True)

        if scored_videos:
            top_threshold = max(len(scored_videos) // 4, 1)
            top_performers = [v for s, v in scored_videos[:top_threshold] if s > 0]

            for v in top_performers:
                v_title = v.get("title", "")
                # Record as winning topic
                await self.brain_repo.record_performance_topic(channel_id, user_id, v_title, is_winning=True)

                # If script exists, extract hook
                s_id = v.get("script_id")
                if s_id:
                    script = await self.script_repo.find_by_id(s_id, user_id=user_id)
                    if script:
                        structured = script.get("structured_data", {})
                        hook = structured.get("selected_hook") or (script.get("script_text", "").split(".")[0] if script.get("script_text") else "")
                        if hook and len(hook) > 10:
                            added = await self.brain_repo.add_winning_hook(channel_id, user_id, hook)
                            if added:
                                winning_hooks_added += 1

            # Synthesize learned rule
            if len(top_performers) >= 1:
                rule_text = f"High retention observed for format '{top_performers[0].get('title', 'Short')[:30]}...' - prioritize fast paced delivery under 45s."
                added_rule = await self.brain_repo.add_learned_rule(channel_id, user_id, rule_text)
                if added_rule:
                    rules_added += 1

        # Fetch updated brain
        updated_brain = await self.brain_repo.find_by_channel(channel_id, user_id)

        return {
            "status": "success",
            "channel_id": channel_id,
            "winning_hooks_added": winning_hooks_added,
            "rules_learned": rules_added,
            "brain_version": updated_brain.get("strategy_version", 1) if updated_brain else 1,
            "brain": serialize_doc(updated_brain) if updated_brain else {}
        }
        
    async def get_channel_memory(self, user_id: str, channel_id: str) -> Optional[dict]:
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            return None
        memory = await self.memory_repo.get_memory(channel_id)
        return serialize_doc(memory)
