import {
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Sliders,
  Sparkles,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  AutopilotConfigPayload,
  configureAutopilot,
  getAutopilotConfig,
  getAutopilotNiches,
  getAutopilotQueue,
  NicheRecommendation,
} from "../api/channels";
import { Channel } from "../types";
import Modal from "./Modal";

interface AutopilotWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
  channel: Channel | null;
  onConfigured: () => void;
}

const COMMON_TIMEZONES = [
  "UTC",
  "Asia/Kolkata",
  "America/New_York",
  "America/Los_Angeles",
  "America/Chicago",
  "Europe/London",
  "Europe/Paris",
  "Asia/Tokyo",
  "Asia/Dubai",
  "Australia/Sydney",
];

const DAYS = [
  { label: "Mon", value: 0 },
  { label: "Tue", value: 1 },
  { label: "Wed", value: 2 },
  { label: "Thu", value: 3 },
  { label: "Fri", value: 4 },
  { label: "Sat", value: 5 },
  { label: "Sun", value: 6 },
];

export const AutopilotWizardModal: React.FC<AutopilotWizardModalProps> = ({
  isOpen,
  onClose,
  channel,
  onConfigured,
}) => {
  const [step, setStep] = useState<number>(1);
  const [loadingNiches, setLoadingNiches] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [niches, setNiches] = useState<NicheRecommendation[]>([]);

  // Wizard state
  const [selectedNiche, setSelectedNiche] = useState<string>("");
  const [customNiche, setCustomNiche] = useState<string>("");
  const [isCustomNiche, setIsCustomNiche] = useState(false);

  const [format, setFormat] = useState<"shorts" | "longform">("shorts");
  const [targetAudience, setTargetAudience] = useState(
    "Tech enthusiasts and developers",
  );
  const [tone, setTone] = useState("informative");
  const [language, setLanguage] = useState("en");
  const [targetGeography, setTargetGeography] = useState("US");
  const [contentPillars, setContentPillars] = useState<string[]>([]);
  const [newPillarInput, setNewPillarInput] = useState("");

  const [timezone, setTimezone] = useState("UTC");
  const [selectedDays, setSelectedDays] = useState<number[]>([0, 2, 4]); // Mon, Wed, Fri
  const [timeStr, setTimeStr] = useState("19:00");
  const [frequency, setFrequency] = useState(3);

  const [mode, setMode] = useState<"full_autopilot" | "assisted" | "off">(
    "full_autopilot",
  );
  const [approvalRequired, setApprovalRequired] = useState(false);
  const [privacyStatus, setPrivacyStatus] = useState<
    "private" | "unlisted" | "public"
  >("private");

  const [queueSlots, setQueueSlots] = useState<any[]>([]);
  const [loadingQueue, setLoadingQueue] = useState(false);

  useEffect(() => {
    if (isOpen && channel) {
      setStep(1);
      loadExistingConfig();
      fetchNiches(false);
      loadQueue();
    }
  }, [isOpen, channel]);

  const loadExistingConfig = async () => {
    if (!channel) return;
    try {
      const data = await getAutopilotConfig(channel.id);
      if (data?.config) {
        const cfg = data.config;
        setSelectedNiche(cfg.niche || "");
        if (cfg.custom_niche) {
          setIsCustomNiche(true);
          setCustomNiche(cfg.custom_niche);
        }
        if (cfg.format) setFormat(cfg.format);
        if (cfg.target_audience) setTargetAudience(cfg.target_audience);
        if (cfg.tone) setTone(cfg.tone);
        if (cfg.language) setLanguage(cfg.language);
        if (cfg.target_geography) setTargetGeography(cfg.target_geography);
        if (cfg.content_pillars) setContentPillars(cfg.content_pillars);
        if (cfg.schedule) {
          if (cfg.schedule.timezone) setTimezone(cfg.schedule.timezone);
          if (cfg.schedule.days_of_week)
            setSelectedDays(cfg.schedule.days_of_week);
          if (cfg.schedule.times && cfg.schedule.times.length > 0)
            setTimeStr(cfg.schedule.times[0]);
          if (cfg.schedule.frequency_per_week)
            setFrequency(cfg.schedule.frequency_per_week);
        }
        if (cfg.mode) setMode(cfg.mode);
        if (cfg.approval_required !== undefined)
          setApprovalRequired(cfg.approval_required);
        if (cfg.privacy_status) setPrivacyStatus(cfg.privacy_status);
      }
    } catch (e) {
      // not yet configured
    }
  };

  const fetchNiches = async (refresh: boolean) => {
    if (!channel) return;
    setLoadingNiches(true);
    try {
      const recs = await getAutopilotNiches(channel.id, refresh);
      setNiches(recs);
      if (recs.length > 0 && !selectedNiche) {
        setSelectedNiche(recs[0].name);
        setContentPillars(recs[0].suggested_pillars || []);
        if (recs[0].target_audience) setTargetAudience(recs[0].target_audience);
      }
    } catch (err: any) {
      toast.error("Failed to load niche recommendations");
    } finally {
      setLoadingNiches(false);
    }
  };

  const loadQueue = async () => {
    if (!channel) return;
    setLoadingQueue(true);
    try {
      const items = await getAutopilotQueue(channel.id);
      setQueueSlots(items);
    } catch (err) {
      // ignore
    } finally {
      setLoadingQueue(false);
    }
  };

  const handleSelectNiche = (nicheObj: NicheRecommendation) => {
    setIsCustomNiche(false);
    setSelectedNiche(nicheObj.name);
    setContentPillars(nicheObj.suggested_pillars || []);
    if (nicheObj.target_audience) setTargetAudience(nicheObj.target_audience);
  };

  const toggleDay = (dayVal: number) => {
    if (selectedDays.includes(dayVal)) {
      if (selectedDays.length === 1) {
        toast.error("At least one publishing day is required.");
        return;
      }
      setSelectedDays(selectedDays.filter((d) => d !== dayVal));
    } else {
      setSelectedDays([...selectedDays, dayVal].sort());
    }
  };

  const addPillar = () => {
    if (!newPillarInput.trim()) return;
    if (contentPillars.includes(newPillarInput.trim())) return;
    setContentPillars([...contentPillars, newPillarInput.trim()]);
    setNewPillarInput("");
  };

  const removePillar = (p: string) => {
    setContentPillars(contentPillars.filter((item) => item !== p));
  };

  const handleConfigure = async () => {
    if (!channel) return;
    const finalNiche = isCustomNiche
      ? customNiche.trim()
      : selectedNiche.trim();
    if (!finalNiche) {
      toast.error("Please select or enter a niche");
      setStep(1);
      return;
    }

    const totalSlots = selectedDays.length * 1;
    if (frequency > totalSlots) {
      toast.error(
        `Frequency (${frequency}/week) exceeds available schedule slots (${totalSlots}/week). Please select more days or reduce frequency.`,
      );
      setStep(3);
      return;
    }

    const payload: AutopilotConfigPayload = {
      mode: mode,
      format: format,
      niche: finalNiche,
      custom_niche: isCustomNiche ? customNiche.trim() : null,
      target_audience: targetAudience,
      tone: tone,
      language: language,
      target_geography: targetGeography,
      content_pillars:
        contentPillars.length > 0 ? contentPillars : [finalNiche],
      schedule: {
        frequency_per_week: frequency,
        timezone: timezone,
        days_of_week: selectedDays,
        times: [timeStr],
      },
      approval_required: mode === "assisted" ? true : approvalRequired,
      privacy_status: privacyStatus,
      tags: [finalNiche.toLowerCase().replace(/[^a-z0-9]/g, "-")],
    };

    setSubmitting(true);
    try {
      const res = await configureAutopilot(channel.id, payload);
      toast.success(res.message || "Autopilot successfully configured!");
      await loadQueue();
      onConfigured();
      setStep(5); // Move to queue preview
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const msg =
        typeof detail === "object"
          ? detail.message
          : detail || "Configuration failed";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Autopilot Setup Wizard: ${channel?.name || "Channel"}`}
    >
      <div className="space-y-5 max-h-[75vh] overflow-y-auto pr-1">
        {/* Wizard Stepper Tabs */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 text-xs">
          {[
            { num: 1, name: "1. Niche" },
            { num: 2, name: "2. Strategy" },
            { num: 3, name: "3. Schedule" },
            { num: 4, name: "4. Mode" },
            { num: 5, name: "5. Queue" },
          ].map((s) => (
            <button
              key={s.num}
              id={`wizard-tab-${s.num}`}
              onClick={() => setStep(s.num)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
                step === s.num
                  ? "bg-blue-600 text-white font-semibold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>

        {/* STEP 1: NICHE DISCOVERY */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  AI Niche Discovery
                </h3>
                <p className="text-xs text-slate-400">
                  Select a high-opportunity niche analyzed from channel context
                  or input a custom niche.
                </p>
              </div>
              <button
                type="button"
                onClick={() => fetchNiches(true)}
                disabled={loadingNiches}
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 border border-slate-700 px-2 py-1 rounded bg-slate-800"
              >
                <RefreshCw
                  className={`w-3 h-3 ${loadingNiches ? "animate-spin" : ""}`}
                />
                Refresh AI
              </button>
            </div>

            {loadingNiches ? (
              <div className="p-8 text-center bg-slate-900/60 rounded-lg border border-slate-800 space-y-2">
                <RefreshCw className="w-6 h-6 animate-spin text-blue-400 mx-auto" />
                <p className="text-xs text-slate-300">
                  Discovering viral YouTube Shorts niches via AI...
                </p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {niches.map((n) => {
                  const isSelected = !isCustomNiche && selectedNiche === n.name;
                  return (
                    <div
                      key={n.id || n.name}
                      data-niche-name={n.name}
                      onClick={() => handleSelectNiche(n)}
                      className={`niche-card p-3 rounded-lg border transition-all cursor-pointer ${
                        isSelected
                          ? "bg-blue-950/40 border-blue-500 ring-1 ring-blue-500"
                          : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <div className="font-semibold text-white text-sm flex items-center gap-2">
                          {n.name}
                          <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {n.source} ({Math.round(n.confidence * 100)}%)
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[11px] font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-2 py-0.5 rounded">
                            Score: {n.opportunity_score}/100
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-300 mb-2">
                        {n.description}
                      </p>
                      {n.suggested_pillars &&
                        n.suggested_pillars.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {n.suggested_pillars.map((p, idx) => (
                              <span
                                key={idx}
                                className="text-[10px] bg-slate-800/80 text-slate-300 px-2 py-0.5 rounded border border-slate-700"
                              >
                                {p}
                              </span>
                            ))}
                          </div>
                        )}
                    </div>
                  );
                })}

                {/* Custom Niche Option */}
                <div
                  onClick={() => setIsCustomNiche(true)}
                  className={`p-3 rounded-lg border transition-all cursor-pointer ${
                    isCustomNiche
                      ? "bg-blue-950/40 border-blue-500 ring-1 ring-blue-500"
                      : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="font-semibold text-white text-sm mb-1.5 flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-blue-400" />
                    Enter Custom Niche
                  </div>
                  {isCustomNiche && (
                    <input
                      type="text"
                      className="input-field mt-2 text-sm"
                      placeholder="e.g. Micro-SaaS Solo Founder Lessons"
                      value={customNiche}
                      onChange={(e) => setCustomNiche(e.target.value)}
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* STEP 2: STRATEGY & AUDIENCE */}
        {step === 2 && (
          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Content Format
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setFormat("shorts")}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    format === "shorts"
                      ? "bg-blue-950/40 border-blue-500 text-white"
                      : "bg-slate-900 border-slate-800 text-slate-400"
                  }`}
                >
                  <div className="font-semibold text-white text-sm">
                    YouTube Shorts (9:16)
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    45-second fast-paced, high retention vertical clips.
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => setFormat("longform")}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    format === "longform"
                      ? "bg-blue-950/40 border-blue-500 text-white"
                      : "bg-slate-900 border-slate-800 text-slate-400"
                  }`}
                >
                  <div className="font-semibold text-white text-sm">
                    Longform (16:9)
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Horizontal deep dives (5-8 minutes).
                  </div>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Tone & Voice
                </label>
                <select
                  className="input-field text-xs py-2"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                >
                  <option value="informative">Informative & Insightful</option>
                  <option value="energetic">High Energy & Hyped</option>
                  <option value="mysterious">Mysterious & Dramatic</option>
                  <option value="provocative">Contrarian & Provocative</option>
                  <option value="humorous">Entertaining & Satirical</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Language
                </label>
                <input
                  type="text"
                  className="input-field text-xs py-2"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  placeholder="en"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Target Audience
              </label>
              <input
                type="text"
                className="input-field text-xs py-2"
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                placeholder="Software engineers, self-taught coders"
              />
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Content Pillars (Rotation)
              </label>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {contentPillars.map((p, idx) => (
                  <span
                    key={idx}
                    className="text-xs bg-slate-800 text-slate-200 px-2.5 py-1 rounded-full border border-slate-700 flex items-center gap-1.5"
                  >
                    {p}
                    <button
                      type="button"
                      onClick={() => removePillar(p)}
                      className="text-slate-400 hover:text-red-400"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  className="input-field text-xs py-1.5"
                  placeholder="Add a content pillar..."
                  value={newPillarInput}
                  onChange={(e) => setNewPillarInput(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && (e.preventDefault(), addPillar())
                  }
                />
                <button
                  type="button"
                  onClick={addPillar}
                  className="btn-secondary text-xs px-3 py-1.5 whitespace-nowrap"
                >
                  Add Pillar
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: SCHEDULE */}
        {step === 3 && (
          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Channel Timezone (IANA)
              </label>
              <select
                id="timezone-select"
                className="input-field text-xs py-2"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
              >
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-slate-400 mt-1">
                Scheduled publishing times are calculated in this local timezone
                and converted to UTC for background workers.
              </p>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Publishing Days of Week
              </label>
              <div className="flex gap-1.5">
                {DAYS.map((d) => {
                  const isSelected = selectedDays.includes(d.value);
                  return (
                    <button
                      type="button"
                      key={d.value}
                      onClick={() => toggleDay(d.value)}
                      className={`flex-1 py-2 text-xs font-semibold rounded border transition-all ${
                        isSelected
                          ? "bg-blue-600 border-blue-500 text-white"
                          : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {d.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Publishing Time ({timezone})
                </label>
                <input
                  type="time"
                  className="input-field text-xs py-2"
                  value={timeStr}
                  onChange={(e) => setTimeStr(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Posts Per Week
                </label>
                <input
                  type="number"
                  min={1}
                  max={selectedDays.length * 1}
                  className="input-field text-xs py-2"
                  value={frequency}
                  onChange={(e) => setFrequency(parseInt(e.target.value) || 1)}
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  Max available: {selectedDays.length} slots/week
                </p>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: MODE & DEFAULTS */}
        {step === 4 && (
          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-300 font-medium mb-2">
                Autonomous Operating Mode
              </label>
              <div className="space-y-2">
                {[
                  {
                    val: "full_autopilot",
                    title: "Full Autopilot (Zero Intervention)",
                    desc: "Autonomous research, script generation, video rendering, and scheduled publishing without waiting for manual confirmation.",
                  },
                  {
                    val: "assisted",
                    title: "Assisted Autopilot (Approval Gate)",
                    desc: "Autonomous creation halts at draft stage, notifying you to review and approve videos before publishing.",
                  },
                  {
                    val: "off",
                    title: "Autopilot Paused",
                    desc: "Keeps configuration and schedule intact, but pauses queue item generation and background execution.",
                  },
                ].map((m) => (
                  <div
                    key={m.val}
                    onClick={() => {
                      setMode(m.val as any);
                      if (m.val === "assisted") setApprovalRequired(true);
                      if (m.val === "full_autopilot")
                        setApprovalRequired(false);
                    }}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      mode === m.val
                        ? "bg-blue-950/40 border-blue-500 ring-1 ring-blue-500"
                        : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="font-semibold text-white text-sm mb-0.5">
                      {m.title}
                    </div>
                    <div className="text-[11px] text-slate-300">{m.desc}</div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                YouTube Privacy Default
              </label>
              <select
                className="input-field text-xs py-2"
                value={privacyStatus}
                onChange={(e) => setPrivacyStatus(e.target.value as any)}
              >
                <option value="private">
                  Private (Only you can view on YouTube)
                </option>
                <option value="unlisted">
                  Unlisted (Anyone with link can view)
                </option>
                <option value="public">
                  Public (Immediately visible to subscribers)
                </option>
              </select>
            </div>
          </div>
        )}

        {/* STEP 5: QUEUE PREVIEW */}
        {step === 5 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-semibold text-white flex items-center gap-1.5">
                  <Calendar className="w-4 h-4 text-emerald-400" />
                  Upcoming 7-Day Autopilot Schedule
                </h4>
                <p className="text-xs text-slate-400">
                  Idempotent, persistent slots scheduled in MongoDB for
                  autonomous production.
                </p>
              </div>
              <button
                type="button"
                onClick={loadQueue}
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 border border-slate-700 px-2 py-1 rounded bg-slate-800"
              >
                <RefreshCw
                  className={`w-3 h-3 ${loadingQueue ? "animate-spin" : ""}`}
                />
                Refresh
              </button>
            </div>

            {loadingQueue ? (
              <div className="p-6 text-center text-xs text-slate-400">
                Loading queue...
              </div>
            ) : queueSlots.length === 0 ? (
              <div className="p-6 text-center bg-slate-900/60 rounded border border-slate-800 text-xs text-slate-400">
                No active slots in the queue. Click "Activate Autopilot" to
                generate the initial schedule.
              </div>
            ) : (
              <div className="space-y-2">
                {queueSlots.map((slot, idx) => (
                  <div
                    key={slot.id || idx}
                    className="queue-slot-item p-3 bg-slate-900/60 border border-slate-800 rounded-lg flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-semibold text-white text-xs">
                        {slot.topic}
                      </div>
                      <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                        <span className="text-blue-400 font-medium">
                          Pillar: {slot.pillar}
                        </span>
                        <span>•</span>
                        <span>
                          {slot.local_time_display ||
                            new Date(slot.scheduled_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-amber-950/40 text-amber-300 border border-amber-800/60">
                      {slot.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Wizard Footer Controls */}
        <div className="pt-4 border-t border-slate-800 flex justify-between items-center">
          <div>
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" /> Back
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary text-xs px-3 py-1.5"
            >
              Close
            </button>
            {step < 4 && (
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                className="btn-primary text-xs px-3 py-1.5 flex items-center gap-1"
              >
                Next <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
            {step >= 4 && (
              <button
                type="button"
                id="save-autopilot-btn"
                onClick={handleConfigure}
                disabled={submitting}
                className="btn-primary text-xs px-4 py-1.5 flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                {submitting ? "Configuring..." : "Save & Activate Autopilot"}
              </button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
};
