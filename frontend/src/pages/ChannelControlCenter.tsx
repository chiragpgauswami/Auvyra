import {
  AlertTriangle,
  ArrowLeft,
  Brain as BrainIcon,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  Film,
  Layers,
  Play,
  RefreshCw,
  RotateCw,
  Shield,
  Sparkles,
  Trash2,
  Tv,
  X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Link, useParams } from "react-router-dom";

import {
  approveQueueSlot,
  AutopilotObservability,
  cancelQueueSlot,
  getAutopilotObservability,
  retryQueueSlot,
  toggleAutopilot,
  triggerSchedulerTick,
} from "../api/autopilot";
import {
  getAutopilotQueue,
  getChannel,
  getChannelBrain,
  getYoutubeStatus,
  syncYoutubeChannel,
  YouTubeStatus,
} from "../api/channels";
import { listVideos } from "../api/videos";
import { AutopilotWizardModal } from "../components/AutopilotWizardModal";
import CaptionStyleSelector from "../components/CaptionStyleSelector";
import StatusBadge from "../components/StatusBadge";
import { AutopilotQueueSlot, Channel, ChannelBrain, Video } from "../types";

export const ChannelControlCenter: React.FC = () => {
  const { channelId } = useParams<{ channelId: string }>();

  const [channel, setChannel] = useState<Channel | null>(null);
  const [brain, setBrain] = useState<ChannelBrain | null>(null);
  const [queue, setQueue] = useState<AutopilotQueueSlot[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [observability, setObservability] =
    useState<AutopilotObservability | null>(null);
  const [youtubeStatus, setYoutubeStatus] = useState<YouTubeStatus | null>(
    null,
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [isWizardOpen, setIsWizardOpen] = useState<boolean>(false);
  const [activeVideoModal, setActiveVideoModal] = useState<Video | null>(null);
  const [toggling, setToggling] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);

  useEffect(() => {
    if (channelId) {
      loadAllData();
    }
  }, [channelId]);

  const loadAllData = async () => {
    if (!channelId) return;
    setLoading(true);
    try {
      const [chanData, brainData, queueData, obsData, vidsData, ytStatus] =
        await Promise.all([
          getChannel(channelId).catch(() => null),
          getChannelBrain(channelId).catch(() => null),
          getAutopilotQueue(channelId).catch(() => []),
          getAutopilotObservability(channelId).catch(() => null),
          listVideos(channelId).catch(() => []),
          getYoutubeStatus().catch(() => null),
        ]);

      setChannel(chanData);
      setBrain(brainData);
      setQueue(queueData);
      setObservability(obsData);
      setVideos(vidsData);
      setYoutubeStatus(ytStatus);
    } catch (err: any) {
      toast.error("Failed to load channel control center");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAutopilot = async () => {
    if (!channel) return;
    setToggling(true);
    const nextState = !channel.autopilot_enabled;
    try {
      await toggleAutopilot(
        channel.id,
        nextState,
        channel.approval_required ?? true,
      );
      toast.success(`Autopilot ${nextState ? "activated" : "paused"}`);
      await loadAllData();
    } catch (err: any) {
      toast.error(
        err.response?.data?.detail?.message || "Failed to toggle Autopilot",
      );
    } finally {
      setToggling(false);
    }
  };

  const handleModeSwitch = async (mode: "assisted" | "full_autopilot") => {
    if (!channel) return;
    try {
      const approvalReq = mode === "assisted";
      await toggleAutopilot(channel.id, channel.autopilot_enabled, approvalReq);
      toast.success(
        `Mode switched to: ${mode === "assisted" ? "Assisted (Approval Gate)" : "Full Autopilot"}`,
      );
      await loadAllData();
    } catch (err: any) {
      toast.error("Failed to switch autopilot mode");
    }
  };

  const handleApproveSlot = async (slotId: string) => {
    const toastId = toast.loading("Approving video for publication...");
    try {
      await approveQueueSlot(slotId);
      toast.success("Video approved! Upload pipeline dispatched.", {
        id: toastId,
      });
      await loadAllData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail?.message || "Approval failed", {
        id: toastId,
      });
    }
  };

  const handleRetrySlot = async (slotId: string) => {
    const toastId = toast.loading("Retrying slot execution...");
    try {
      await retryQueueSlot(slotId);
      toast.success("Slot re-enqueued for production!", { id: toastId });
      await loadAllData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail?.message || "Retry failed", {
        id: toastId,
      });
    }
  };

  const handleCancelSlot = async (slotId: string) => {
    if (!window.confirm("Are you sure you want to cancel this scheduled slot?"))
      return;
    try {
      await cancelQueueSlot(slotId);
      toast.success("Scheduled slot cancelled");
      await loadAllData();
    } catch (err: any) {
      toast.error("Failed to cancel slot");
    }
  };

  const handleManualSync = async () => {
    if (!channel) return;
    setSyncing(true);
    try {
      await syncYoutubeChannel();
      toast.success("YouTube channel data synchronized!");
      await loadAllData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail?.message || "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleSchedulerTick = async () => {
    try {
      await triggerSchedulerTick();
      toast.success("Scheduler evaluated: replenished bounded queue.");
      await loadAllData();
    } catch (err: any) {
      toast.error("Scheduler tick failed");
    }
  };

  if (loading || !channel) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin mr-3 text-blue-500" />
        Loading Channel Control Center...
      </div>
    );
  }

  const isAssisted = Boolean(
    channel.approval_required ??
    (channel as any).autopilot_config?.approval_required,
  );
  const config = (channel as any).autopilot_config || {};
  const schedule = config.schedule || {};
  const nextSlot = queue.find(
    (q) =>
      q.status === "pending" ||
      q.status === "ready_for_approval" ||
      q.status.startsWith("producing_"),
  );

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-12">
      {/* Top Breadcrumb & Actions */}
      <div className="flex items-center justify-between">
        <Link
          to="/channels"
          className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Channels
        </Link>
        <div className="flex items-center gap-3">
          <button
            onClick={handleManualSync}
            disabled={syncing}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded-lg text-sm border border-slate-700 transition"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${syncing ? "animate-spin text-blue-400" : ""}`}
            />
            Sync YouTube
          </button>
          <button
            onClick={handleSchedulerTick}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded-lg text-sm border border-slate-700 transition"
          >
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            Trigger Scheduler
          </button>
        </div>
      </div>

      {/* 1. Header & Identity Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            {channel.thumbnail_url ? (
              <img
                src={channel.thumbnail_url}
                alt={channel.name}
                className="w-20 h-20 rounded-2xl border-2 border-slate-700 object-cover shadow-lg"
              />
            ) : (
              <div className="w-20 h-20 rounded-2xl bg-blue-600/20 border-2 border-blue-500/40 flex items-center justify-center text-blue-400">
                <Tv className="w-10 h-10" />
              </div>
            )}
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-white tracking-tight">
                  {channel.name}
                </h1>
                <span
                  className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-semibold ${
                    channel.status === "connected"
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      : "bg-red-500/10 text-red-400 border border-red-500/30"
                  }`}
                >
                  {channel.status === "connected" ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5" />
                  )}
                  {channel.status === "connected"
                    ? "YouTube Linked"
                    : "Disconnected"}
                </span>
              </div>
              <p className="text-sm text-slate-400 font-mono mt-1">
                {channel.handle
                  ? `@${channel.handle.replace(/^@/, "")}`
                  : `ID: ${channel.youtube_channel_id || channel.id}`}
              </p>
              {/* Channel Stats Badges */}
              <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-slate-300">
                <span className="bg-slate-800/80 px-2.5 py-1 rounded-md border border-slate-700/60">
                  <strong className="text-white font-semibold">
                    {channel.subscriber_count?.toLocaleString() || 0}
                  </strong>{" "}
                  Subscribers
                </span>
                <span className="bg-slate-800/80 px-2.5 py-1 rounded-md border border-slate-700/60">
                  <strong className="text-white font-semibold">
                    {channel.video_count?.toLocaleString() || 0}
                  </strong>{" "}
                  Videos
                </span>
                <span className="bg-slate-800/80 px-2.5 py-1 rounded-md border border-slate-700/60">
                  <strong className="text-white font-semibold">
                    {channel.view_count?.toLocaleString() || 0}
                  </strong>{" "}
                  Lifetime Views
                </span>
              </div>
            </div>
          </div>

          {/* Autopilot Master Toggle & Mode */}
          <div className="flex flex-col items-end gap-3 bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-slate-300">
                Autopilot System
              </span>
              <button
                onClick={handleToggleAutopilot}
                disabled={toggling}
                className={`relative inline-flex h-7 w-14 items-center rounded-full transition-colors focus:outline-none ${
                  channel.autopilot_enabled ? "bg-blue-600" : "bg-slate-700"
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
                    channel.autopilot_enabled
                      ? "translate-x-8"
                      : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            {/* Assisted vs Full Autopilot Mode Buttons */}
            <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs">
              <button
                onClick={() => handleModeSwitch("assisted")}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  isAssisted
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Assisted (Review Gate)
              </button>
              <button
                onClick={() => handleModeSwitch("full_autopilot")}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  !isAssisted
                    ? "bg-purple-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Full Autopilot
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Grid: Strategy & Config (Niche + Schedule + Pillars) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Niche & Target Audience */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              Niche & Audience
            </span>
            <button
              onClick={() => setIsWizardOpen(true)}
              className="text-xs text-blue-400 hover:text-blue-300 font-medium"
            >
              Reconfigure
            </button>
          </div>
          <div className="text-xl font-bold text-white">
            {config.niche || brain?.niche || "General Tech & AI"}
          </div>
          <p className="text-xs text-slate-400">
            Target Audience:{" "}
            <span className="text-slate-300 font-medium">
              {config.target_audience || "General Shorts Viewers"}
            </span>
          </p>
          <div className="flex flex-wrap gap-1.5 pt-2">
            {(config.content_pillars || []).map((p: string, idx: number) => (
              <span
                key={idx}
                className="bg-slate-800 text-slate-300 text-xs px-2.5 py-0.5 rounded-full border border-slate-700/60"
              >
                {p}
              </span>
            ))}
          </div>
        </div>

        {/* Schedule & Timing */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-blue-400" />
              Publishing Schedule
            </span>
            <span className="text-xs text-slate-400 font-mono">
              {schedule.timezone || "UTC"}
            </span>
          </div>
          <div className="text-xl font-bold text-white">
            {schedule.frequency_per_week || 3} Shorts / week
          </div>
          <p className="text-xs text-slate-400">
            Release Times:{" "}
            <span className="text-slate-300 font-medium">
              {(schedule.times || ["19:00"]).join(", ")}
            </span>
          </p>
          <div className="text-xs text-slate-400 pt-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Bounded 7-day auto replenishment active
          </div>
        </div>

        {/* Next Scheduled Video Countdown */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-emerald-400" />
            Next Scheduled Slot
          </span>
          {nextSlot ? (
            <div>
              <div className="text-lg font-bold text-white truncate">
                {nextSlot.topic}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                {nextSlot.local_time_display ||
                  (nextSlot.scheduled_at
                    ? new Date(nextSlot.scheduled_at).toLocaleString()
                    : nextSlot.slot_date)}
              </p>
              <div className="mt-3">
                <StatusBadge status={nextSlot.status} />
              </div>
            </div>
          ) : (
            <div className="text-slate-500 text-sm py-4">
              No upcoming slots currently queued.
            </div>
          )}
        </div>
      </div>

      {/* Caption Style Studio */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-lg">
        <CaptionStyleSelector
          channelId={channel.id}
          onStyleSaved={() => loadAllData()}
        />
      </div>

      {/* Production Queue Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-blue-400" />
              Autonomous Production Queue
            </h3>
            <p className="text-sm text-slate-400">
              Granular stages with persistent checkpoints, worker leases, and
              review gates.
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400 bg-slate-800 px-3 py-1 rounded-full">
            {queue.length} Total Slots
          </span>
        </div>

        {queue.length === 0 ? (
          <div className="text-center py-10 text-slate-500">
            No production slots found. Trigger the scheduler or reconfigure
            Autopilot to bootstrap the queue.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/70 text-xs uppercase text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Scheduled Release</th>
                  <th className="py-3 px-4">Pillar & Topic</th>
                  <th className="py-3 px-4">Current Stage / Status</th>
                  <th className="py-3 px-4">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {queue.map((slot) => (
                  <tr
                    key={slot.id}
                    className="hover:bg-slate-850/50 transition"
                  >
                    <td className="py-3 px-4 font-mono text-xs whitespace-nowrap">
                      {slot.local_time_display ||
                        (slot.scheduled_at
                          ? new Date(slot.scheduled_at).toLocaleDateString()
                          : slot.slot_date)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-white">{slot.topic}</div>
                      <span className="text-xs text-slate-400">
                        {slot.pillar}
                      </span>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <StatusBadge status={slot.status} />
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {slot.status === "ready_for_approval" && (
                          <button
                            onClick={() => handleApproveSlot(slot.id)}
                            className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3 py-1 rounded font-medium flex items-center gap-1 shadow"
                          >
                            <Check className="w-3 h-3" /> Approve Upload
                          </button>
                        )}
                        {(slot.status === "failed" ||
                          slot.status === "retrying") && (
                          <button
                            onClick={() => handleRetrySlot(slot.id)}
                            className="bg-amber-600 hover:bg-amber-500 text-white text-xs px-3 py-1 rounded font-medium flex items-center gap-1"
                          >
                            <RotateCw className="w-3 h-3" /> Retry
                          </button>
                        )}
                        {slot.status === "pending" && (
                          <button
                            onClick={() => handleCancelSlot(slot.id)}
                            className="text-slate-400 hover:text-red-400 text-xs p-1"
                            title="Cancel Slot"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {slot.youtube_url && (
                          <a
                            href={slot.youtube_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300 text-xs flex items-center gap-1 font-medium"
                          >
                            View YouTube <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Grid: Recent Videos & Channel Brain Signals */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Generated Videos */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Film className="w-5 h-5 text-purple-400" />
            Recent Composed Videos
          </h3>

          {videos.length === 0 ? (
            <p className="text-sm text-slate-500 py-6">
              No videos rendered yet for this channel.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {videos.slice(0, 4).map((v) => (
                <div
                  key={v.id}
                  onClick={() => setActiveVideoModal(v)}
                  className="group bg-slate-950/80 border border-slate-800 rounded-xl p-3 cursor-pointer hover:border-blue-500/50 transition duration-200"
                >
                  <div className="relative aspect-[9/16] bg-slate-900 rounded-lg overflow-hidden mb-2">
                    {v.thumbnail_path ? (
                      <img
                        src={`/${v.thumbnail_path}`}
                        alt={v.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-slate-600">
                        <Play className="w-8 h-8" />
                      </div>
                    )}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition">
                      <Play className="w-10 h-10 text-white drop-shadow-md" />
                    </div>
                  </div>
                  <div className="text-xs font-semibold text-white truncate">
                    {v.title}
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1">
                    <span>
                      {v.duration ? `${Math.round(v.duration)}s` : "45s"}
                    </span>
                    <StatusBadge status={v.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Channel Brain Intelligence Feed */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <BrainIcon className="w-5 h-5 text-emerald-400" />
              Channel Brain Evidence Signals
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              Strategy v{brain?.strategy_version || 1}
            </span>
          </div>

          <div className="space-y-3">
            {/* Winning Hooks */}
            <div>
              <span className="text-xs font-semibold uppercase text-slate-400">
                Winning Opening Hooks
              </span>
              <div className="mt-1.5 space-y-1.5">
                {(brain?.winning_hooks || [])
                  .slice(0, 3)
                  .map((hook: any, i) => (
                    <div
                      key={i}
                      className="text-xs bg-slate-950/70 border border-slate-800/80 p-2.5 rounded-lg text-emerald-300 font-medium"
                    >
                      "
                      {typeof hook === "string"
                        ? hook
                        : hook.pattern ||
                          hook.hook_type ||
                          JSON.stringify(hook)}
                      "
                    </div>
                  ))}
                {(!brain?.winning_hooks ||
                  brain.winning_hooks.length === 0) && (
                  <p className="text-xs text-slate-500">
                    Awaiting initial video performance data to extract winning
                    hooks.
                  </p>
                )}
              </div>
            </div>

            {/* Learned Rules */}
            <div className="pt-2">
              <span className="text-xs font-semibold uppercase text-slate-400">
                Learned Production Rules
              </span>
              <div className="mt-1.5 space-y-1.5">
                {(brain?.learned_rules || []).slice(0, 3).map((rule, i) => (
                  <div
                    key={i}
                    className="text-xs bg-slate-950/70 border border-slate-800/80 p-2.5 rounded-lg text-blue-300"
                  >
                    {rule}
                  </div>
                ))}
                {(!brain?.learned_rules ||
                  brain.learned_rules.length === 0) && (
                  <p className="text-xs text-slate-500">
                    Autonomous learning loop synthesizes rules after each video
                    publish.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Production Telemetry & Observability Feed */}
      {observability && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            Operational Telemetry & Stage Audit
          </h3>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
            <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400">Pending Slots</span>
              <div className="text-xl font-bold text-white">
                {observability.queue_depth?.pending || 0}
              </div>
            </div>
            <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400">Producing</span>
              <div className="text-xl font-bold text-blue-400">
                {observability.queue_depth?.in_production || 0}
              </div>
            </div>
            <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400">Awaiting Review</span>
              <div className="text-xl font-bold text-amber-400">
                {observability.queue_depth?.ready_for_approval || 0}
              </div>
            </div>
            <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400">Published</span>
              <div className="text-xl font-bold text-emerald-400">
                {observability.queue_depth?.published || 0}
              </div>
            </div>
          </div>

          {/* Event Stream Log */}
          <div className="mt-4">
            <span className="text-xs font-semibold uppercase text-slate-400 mb-2 block">
              Recent Stage Events
            </span>
            <div className="bg-slate-950/80 rounded-xl p-3 max-h-48 overflow-y-auto space-y-1.5 font-mono text-xs text-slate-400 border border-slate-800">
              {(observability.recent_events || []).map((ev, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border-b border-slate-850 pb-1"
                >
                  <span className="text-slate-300">
                    <span className="text-blue-400 font-semibold">
                      {ev.stage}
                    </span>
                    : {ev.message}
                  </span>
                  <span className="text-slate-500 text-[11px] whitespace-nowrap">
                    {new Date(ev.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Autopilot Setup Modal */}
      {isWizardOpen && (
        <AutopilotWizardModal
          isOpen={isWizardOpen}
          channel={channel}
          onClose={() => setIsWizardOpen(false)}
          onConfigured={() => {
            setIsWizardOpen(false);
            loadAllData();
          }}
        />
      )}

      {/* Video Preview Player Modal */}
      {activeVideoModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-5 space-y-4 relative shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-white text-base truncate">
                {activeVideoModal.title}
              </h3>
              <button
                onClick={() => setActiveVideoModal(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="aspect-[9/16] max-h-[65vh] mx-auto bg-black rounded-xl overflow-hidden flex items-center justify-center">
              {activeVideoModal.file_path ? (
                <video
                  src={`/${activeVideoModal.file_path}`}
                  controls
                  autoPlay
                  className="w-full h-full object-contain"
                />
              ) : (
                <p className="text-sm text-slate-500">Video file not found.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChannelControlCenter;
