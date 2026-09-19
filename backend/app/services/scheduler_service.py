"""
Autopilot Scheduler Service (Phase 20).
Enforces bounded 7-day queue replenishment, per-channel concurrency control (max 1),
worker lease reclamation, and separate scheduling from production execution.
"""

import zoneinfo
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId
from loguru import logger

from backend.app.repositories.channels import ChannelRepository, AutopilotQueueRepository
from backend.app.repositories.jobs import JobRepository
from backend.app.repositories.caption_styles import CaptionStyleRepository
from backend.app.models.channel import AutopilotMode
from backend.app.models.job import JobType

class SchedulerService:
    def __init__(self, db):
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.queue_repo = AutopilotQueueRepository(db)
        self.job_repo = JobRepository(db)
        self.caption_repo = CaptionStyleRepository(db)


    async def tick(self, now_utc: Optional[datetime] = None, max_global: int = 2) -> Dict[str, Any]:
        """
        Executes one scheduler evaluation tick:
        1. Reclaims expired worker leases.
        2. Replenishes 7-day bounded queue for eligible channels.
        3. Enqueues due slots for production workers while respecting concurrency boundaries.
        """
        now = now_utc or datetime.now(timezone.utc)

        reclaimed = await self.reclaim_expired_leases(now)
        replenished = await self.replenish_queues(now)
        claimed_slots = await self.find_and_claim_due_slots(now, max_global=max_global)

        return {
            "reclaimed_leases": reclaimed,
            "replenished_slots": replenished,
            "claimed_slots": claimed_slots,
            "timestamp": now.isoformat()
        }

    async def reclaim_expired_leases(self, now_utc: datetime) -> int:
        """Finds slots stuck in_production with expired leases and resets or fails them."""
        return await self.queue_repo.reclaim_expired_leases(now_utc)

    async def replenish_queues(self, now_utc: datetime) -> int:
        """
        Maintains a bounded 7-day future queue for ASSISTED and FULL_AUTOPILOT channels.
        OFF channels are skipped. Uses (channel_id, scheduled_at) idempotency boundary.
        """
        # Find active connected channels with autopilot enabled
        cursor = self.db.channels.find({
            "status": "connected",
            "autopilot_enabled": True
        })
        channels = await cursor.to_list(length=200)

        total_replenished = 0
        for channel in channels:
            config = channel.get("autopilot_config", {})
            mode = config.get("mode", "full_autopilot")
            if mode == "off" or mode == AutopilotMode.off.value:
                continue

            schedule = config.get("schedule", {})
            freq = schedule.get("frequency_per_week", 3)
            tz_str = schedule.get("timezone", "UTC")
            days_of_week = schedule.get("days_of_week", [0, 2, 4])
            times = schedule.get("times", ["19:00"])
            pillars = config.get("content_pillars", ["General Breakdown"])
            channel_id = str(channel["_id"])
            user_id = channel["user_id"]

            try:
                local_tz = zoneinfo.ZoneInfo(tz_str)
            except Exception:
                local_tz = zoneinfo.ZoneInfo("UTC")

            # Check existing upcoming slots in the next 7 days
            seven_days_future = now_utc + timedelta(days=7)
            existing_count = await self.db.autopilot_queue.count_documents({
                "channel_id": channel_id,
                "scheduled_at": {"$gt": now_utc, "$lte": seven_days_future},
                "status": {"$in": ["pending", "in_production", "ready_for_approval"]}
            })

            if existing_count < freq:
                needed = freq - existing_count
                now_local = now_utc.astimezone(local_tz)

                candidate_slots = []
                for day_offset in range(1, 8):
                    cand_date = now_local.date() + timedelta(days=day_offset)
                    if cand_date.weekday() in days_of_week:
                        for t_str in times:
                            try:
                                h, m = map(int, t_str.split(":"))
                                cand_dt = datetime(cand_date.year, cand_date.month, cand_date.day, h, m, tzinfo=local_tz)
                                candidate_slots.append(cand_dt)
                            except Exception:
                                pass

                candidate_slots.sort()

                caption_cfg = await self.caption_repo.get_channel_style(channel_id, user_id)

                created_for_chan = 0
                for cand_dt in candidate_slots:
                    if created_for_chan >= needed:
                        break

                    cand_utc = cand_dt.astimezone(timezone.utc)
                    # Check idempotency boundary: (channel_id, scheduled_at)
                    existing = await self.queue_repo.find_slot(channel_id, cand_utc)
                    if not existing:
                        pillar_choice = pillars[created_for_chan % len(pillars)]
                        slot_doc = {
                            "user_id": user_id,
                            "channel_id": channel_id,
                            "scheduled_at": cand_utc,
                            "local_time_display": cand_dt.strftime("%A %b %d at %H:%M %Z"),
                            "timezone": tz_str,
                            "format": config.get("format", "shorts"),
                            "pillar": pillar_choice,
                            "topic": f"Breakthroughs in {pillar_choice}",
                            "caption_style_config": caption_cfg,
                            "status": "pending",
                            "priority": 1,
                            "source": "scheduler_replenish",
                            "config_version": config.get("config_version", 1),
                            "stages": {},
                            "attempts": 0,
                            "max_attempts": 3,
                            "artifacts": {},
                            "created_at": now_utc,
                            "updated_at": now_utc
                        }
                        await self.queue_repo.create_slot(slot_doc)
                        created_for_chan += 1
                        total_replenished += 1


        return total_replenished

    async def find_and_claim_due_slots(self, now_utc: datetime, max_global: int = 2) -> List[str]:
        """
        Atomically claims due slots for production execution.
        Enforces global max concurrency and per-channel concurrency (strictly 1).
        Enqueues claimed slots into the jobs collection for AutopilotWorker.
        """
        # Check global active concurrency
        active_global = await self.db.autopilot_queue.count_documents({"status": "in_production"})
        available_global_slots = max(0, max_global - active_global)
        if available_global_slots <= 0:
            return []

        # Find candidates: pending slots due for execution
        cursor = self.db.autopilot_queue.find({
            "status": "pending",
            "scheduled_at": {"$lte": now_utc}
        }).sort("scheduled_at", 1).limit(available_global_slots * 2)

        candidates = await cursor.to_list(length=available_global_slots * 2)
        claimed_ids = []

        for cand in candidates:
            if len(claimed_ids) >= available_global_slots:
                break

            channel_id = cand["channel_id"]
            slot_id = str(cand["_id"])

            # Per-channel concurrency control: max 1 per channel
            active_in_chan = await self.queue_repo.count_active_channel_slots(channel_id)
            if active_in_chan >= 1:
                continue

            # Atomically claim slot with lease
            worker_id = f"worker_{datetime.now(timezone.utc).timestamp()}"
            claimed = await self.queue_repo.claim_due_slot(worker_id=worker_id, now_utc=now_utc)
            if claimed:
                claimed_ids.append(str(claimed["_id"]))

                # Enqueue into jobs collection for AutopilotWorker
                await self.job_repo.enqueue(
                    job_type=JobType.autopilot_orchestration.value,
                    user_id=cand["user_id"],
                    channel_id=channel_id,
                    payload={"queue_item_id": str(claimed["_id"]), "worker_id": worker_id}
                )

        return claimed_ids

