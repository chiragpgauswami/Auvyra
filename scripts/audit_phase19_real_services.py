"""
Phase 19 Real Acceptance Audit Script
Exercises:
1. Real Ollama live inference (llama3.1:8b)
2. Fallback to curated_heuristic when Ollama is unavailable
3. Real MongoDB persistence (channels, channel_brains, autopilot_queue)
4. Timezone-aware scheduling arithmetic (Asia/Kolkata 19:00 IST -> 13:30 UTC)
5. Queue idempotency (re-configuring creates 0 duplicate slots)
6. Multi-tenant and cross-channel isolation
7. Non-destructive mode transitions (full_autopilot -> assisted -> off)
8. Error semantics (invalid timezone 422, invalid schedule 400, unauthorized 404)
"""

import asyncio
import httpx
from datetime import datetime, timezone
import zoneinfo
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from backend.app.config import get_settings
from backend.app.ai.gateway import AIGateway
from backend.app.models.channel import AutopilotConfig, AutopilotMode, ContentFormat

BASE_URL = "http://127.0.0.1:8000"
MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "auvyra"

audit_results = {}

async def run_audit():
    print("==================================================================")
    print("   PHASE 19 REAL SERVICE ACCEPTANCE AUDIT")
    print("==================================================================")

    settings = get_settings()
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as http:
        # -------------------------------------------------------------
        # 1. REAL OLLAMA LIVE INFERENCE
        # -------------------------------------------------------------
        print("\n--- [1/8] AUDITING REAL OLLAMA INFERENCE ---")
        ai_live = AIGateway(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL)
        live_channel_context = {
            "channel_id": "audit_real_ch1",
            "name": "AI Systems & Robotics",
            "description": "Autonomous agents, reinforcement learning, and humanoid robotics."
        }
        res_live = await ai_live.generate_niche_recommendations(live_channel_context)
        print(f"Ollama Model:        {settings.OLLAMA_MODEL}")
        print(f"Ollama URL:          {settings.OLLAMA_BASE_URL}")
        print(f"Niches Returned:     {len(res_live)}")
        if res_live:
            first = res_live[0]
            print(f"Sample Niche:        {first.get('name')}")
            print(f"Source Field:        {first.get('source')}")
            print(f"Confidence:          {first.get('confidence')}")
            print(f"Opportunity Score:   {first.get('opportunity_score')}")
            print(f"Pillars:             {first.get('suggested_pillars')}")
            assert first.get("source") == "ollama", f"Expected 'ollama' source, got {first.get('source')}"
            assert first.get("confidence") > 0.8
            assert first.get("opportunity_score") >= 50
            audit_results["Real Ollama Live Inference"] = "PASS"
        else:
            audit_results["Real Ollama Live Inference"] = "FAIL"

        # -------------------------------------------------------------
        # 2. OLLAMA UNAVAILABLE FALLBACK
        # -------------------------------------------------------------
        print("\n--- [2/8] AUDITING OLLAMA UNAVAILABLE FALLBACK ---")
        ai_fallback = AIGateway(base_url="http://localhost:11435", model="llama3.1:8b")
        res_fallback = await ai_fallback.generate_niche_recommendations(live_channel_context)
        print(f"Fallback Returned:   {len(res_fallback)}")
        fb_first = res_fallback[0]
        print(f"Fallback Source:     {fb_first.get('source')}")
        print(f"Fallback Confidence: {fb_first.get('confidence')}")
        print(f"Fallback Score:      {fb_first.get('opportunity_score')}")
        assert fb_first.get("source") == "curated_heuristic"
        assert fb_first.get("confidence") == 0.75
        audit_results["Ollama Fallback to Heuristic"] = "PASS"

        # -------------------------------------------------------------
        # 3. REGISTRATION & CHANNEL SETUP FOR USER A & USER B
        # -------------------------------------------------------------
        print("\n--- [3/8] REGISTERING TEST TENANTS ---")
        import time
        ts = time.time_ns()
        reg_a = await http.post("/api/auth/register", json={
            "email": f"audit_user_a_{ts}@example.com",
            "password": "Password123!Secure",
            "name": "Audit User A"
        })
        assert reg_a.status_code == 201, f"User A registration failed: {reg_a.status_code} - {reg_a.text}"
        token_a = reg_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        ch_a1 = (await http.post("/api/channels/", json={
            "name": "Edge AI Systems",
            "description": "On-device intelligence and edge robotics"
        }, headers=headers_a)).json()
        ch_a1_id = ch_a1["id"]

        ch_a2 = (await http.post("/api/channels/", json={
            "name": "Quantum Computing Daily",
            "description": "Qubits and quantum algorithms"
        }, headers=headers_a)).json()
        ch_a2_id = ch_a2["id"]

        reg_b = await http.post("/api/auth/register", json={
            "email": f"audit_user_b_{ts}@example.com",
            "password": "Password123!Secure",
            "name": "Audit User B"
        })
        assert reg_b.status_code == 201, f"User B registration failed: {reg_b.status_code} - {reg_b.text}"
        token_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        print(f"User A Registered: Channel 1={ch_a1_id}, Channel 2={ch_a2_id}")
        print(f"User B Registered.")

        # -------------------------------------------------------------
        # 4. TIMEZONE-AWARE SCHEDULING (Asia/Kolkata 19:00 IST -> 13:30 UTC)
        # -------------------------------------------------------------
        print("\n--- [4/8] AUDITING TIMEZONE-AWARE SCHEDULING ---")
        config_payload = {
            "mode": "full_autopilot",
            "format": "shorts",
            "niche": "Edge AI Systems",
            "custom_niche": None,
            "target_audience": "Embedded engineers and AI developers",
            "tone": "authoritative",
            "language": "en",
            "target_geography": "IN",
            "content_pillars": ["NPU Architectures", "TinyML Optimization", "Edge Robotics"],
            "schedule": {
                "frequency_per_week": 3,
                "timezone": "Asia/Kolkata",
                "days_of_week": [0, 2, 4],  # Mon, Wed, Fri
                "times": ["19:00"]
            },
            "approval_required": False,
            "privacy_status": "private",
            "tags": ["edge-ai", "tinyml", "robotics"]
        }

        cfg_res = await http.post(f"/api/channels/{ch_a1_id}/autopilot/configure", json=config_payload, headers=headers_a)
        assert cfg_res.status_code == 200, f"Configure failed: {cfg_res.text}"
        cfg_data = cfg_res.json()
        print(f"Scheduled Slots Generated: {cfg_data['scheduled_slots_count']}")
        assert cfg_data["scheduled_slots_count"] == 3

        # Verify MongoDB slots
        slots = await db.autopilot_queue.find({"channel_id": ch_a1_id}).sort("scheduled_at", 1).to_list(10)
        assert len(slots) == 3
        for s in slots:
            dt_utc = s["scheduled_at"]
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            dt_ist = dt_utc.astimezone(zoneinfo.ZoneInfo("Asia/Kolkata"))
            print(f"  Slot: UTC={dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} | IST={dt_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            assert dt_ist.hour == 19 and dt_ist.minute == 0, f"Expected 19:00 IST, got {dt_ist}"
            assert dt_utc.hour == 13 and dt_utc.minute == 30, f"Expected 13:30 UTC, got {dt_utc}"
            assert s["format"] == "shorts"
            assert s["status"] == "pending"
            assert s["pillar"] in ["NPU Architectures", "TinyML Optimization", "Edge Robotics"]

        audit_results["Timezone-Aware Scheduling (Asia/Kolkata 19:00 = 13:30 UTC)"] = "PASS"

        # -------------------------------------------------------------
        # 5. REAL MONGODB PERSISTENCE & SCHEMAS
        # -------------------------------------------------------------
        print("\n--- [5/8] AUDITING REAL MONGODB PERSISTENCE ---")
        chan_doc = await db.channels.find_one({"_id": ObjectId(ch_a1_id)})
        assert chan_doc["autopilot_enabled"] is True
        assert chan_doc["autopilot_config"]["mode"] == "full_autopilot"
        assert chan_doc["autopilot_config"]["schedule"]["timezone"] == "Asia/Kolkata"

        brain_doc = await db.channel_brains.find_one({"channel_id": ch_a1_id})
        assert brain_doc is not None
        assert brain_doc["niche"] == "Edge AI Systems"
        assert len(brain_doc["content_pillars"]) == 3
        assert brain_doc["publishing_strategy"]["timezone"] == "Asia/Kolkata"
        assert brain_doc["format_strategy"]["target_duration_seconds"] == 45

        print("  ✓ channels doc verified.")
        print("  ✓ channel_brains doc verified.")
        print("  ✓ autopilot_queue docs verified.")
        audit_results["MongoDB Document Scoping & Persistence"] = "PASS"

        # -------------------------------------------------------------
        # 6. IDEMPOTENCY AUDIT
        # -------------------------------------------------------------
        print("\n--- [6/8] AUDITING QUEUE IDEMPOTENCY ---")
        cfg_res_2 = await http.post(f"/api/channels/{ch_a1_id}/autopilot/configure", json=config_payload, headers=headers_a)
        assert cfg_res_2.status_code == 200
        new_slots_count = cfg_res_2.json()["scheduled_slots_count"]
        print(f"Re-configuration new slots: {new_slots_count} (Expected 0)")
        total_slots_count = await db.autopilot_queue.count_documents({"channel_id": ch_a1_id})
        assert total_slots_count == 3, f"Expected 3 slots, found {total_slots_count}"
        assert new_slots_count == 0
        audit_results["Queue Bootstrap Idempotency"] = "PASS"

        # -------------------------------------------------------------
        # 7. MULTI-TENANT & CROSS-CHANNEL ISOLATION
        # -------------------------------------------------------------
        print("\n--- [7/8] AUDITING MULTI-TENANT & CHANNEL ISOLATION ---")
        # User B cannot get niches for User A's channel
        r_iso_niches = await http.get(f"/api/channels/{ch_a1_id}/autopilot/niches", headers=headers_b)
        assert r_iso_niches.status_code == 404

        # User B cannot configure User A's channel
        r_iso_cfg = await http.post(f"/api/channels/{ch_a1_id}/autopilot/configure", json=config_payload, headers=headers_b)
        assert r_iso_cfg.status_code == 404

        # User B cannot read User A's queue
        r_iso_q = await http.get(f"/api/channels/{ch_a1_id}/autopilot/queue", headers=headers_b)
        assert r_iso_q.status_code == 404

        # Channel 2 of User A has 0 queue slots
        ch2_q = (await http.get(f"/api/channels/{ch_a2_id}/autopilot/queue", headers=headers_a)).json()
        assert len(ch2_q) == 0

        print("  ✓ Cross-user isolation verified (404 on all endpoints).")
        print("  ✓ Cross-channel isolation verified.")
        audit_results["Multi-Tenant and Channel Isolation"] = "PASS"

        # -------------------------------------------------------------
        # 8. ERROR SEMANTICS & MODE SWITCHING
        # -------------------------------------------------------------
        print("\n--- [8/8] AUDITING ERROR SEMANTICS & MODE TRANSITIONS ---")
        # Invalid timezone -> 422
        bad_tz_payload = dict(config_payload)
        bad_tz_payload["schedule"] = dict(config_payload["schedule"])
        bad_tz_payload["schedule"]["timezone"] = "Atlantis/City"
        r_err_tz = await http.post(f"/api/channels/{ch_a1_id}/autopilot/configure", json=bad_tz_payload, headers=headers_a)
        assert r_err_tz.status_code == 422, f"Expected 422 for bad timezone, got {r_err_tz.status_code}"

        # Frequency exceeds slots -> 400
        bad_freq_payload = dict(config_payload)
        bad_freq_payload["schedule"] = dict(config_payload["schedule"])
        bad_freq_payload["schedule"]["frequency_per_week"] = 10
        r_err_freq = await http.post(f"/api/channels/{ch_a1_id}/autopilot/configure", json=bad_freq_payload, headers=headers_a)
        assert r_err_freq.status_code == 400, f"Expected 400 for frequency excess, got {r_err_freq.status_code}"

        # Non-destructive mode transitions
        # Switch to assisted
        config_payload["mode"] = "assisted"
        await http.post(f"/api/channels/{ch_a1_id}/autopilot/configure", json=config_payload, headers=headers_a)
        c_assisted = await db.channels.find_one({"_id": ObjectId(ch_a1_id)})
        assert c_assisted["autopilot_config"]["mode"] == "assisted"

        # Switch to off
        config_payload["mode"] = "off"
        await http.post(f"/api/channels/{ch_a1_id}/autopilot/configure", json=config_payload, headers=headers_a)
        c_off = await db.channels.find_one({"_id": ObjectId(ch_a1_id)})
        assert c_off["autopilot_config"]["mode"] == "off"
        assert c_off["autopilot_enabled"] is False

        # Verify slots still intact
        slots_after_off = await db.autopilot_queue.count_documents({"channel_id": ch_a1_id})
        assert slots_after_off == 3
        print("  ✓ Error semantics verified (422 invalid timezone, 400 invalid schedule).")
        print("  ✓ Non-destructive mode transitions verified.")
        audit_results["Error Semantics & Mode Switching"] = "PASS"

    print("\n==================================================================")
    print("   PHASE 19 REAL SERVICE AUDIT SUMMARY")
    print("==================================================================")
    for k, v in audit_results.items():
        print(f"  [{v}] {k}")
    print("==================================================================")

if __name__ == "__main__":
    asyncio.run(run_audit())
