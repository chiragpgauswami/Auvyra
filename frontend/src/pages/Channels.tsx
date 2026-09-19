import {
  AlertTriangle,
  CheckCircle2,
  Plus,
  RefreshCw,
  Sliders,
  Tv,
  Unlink,
  Zap,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { toggleAutopilot, triggerAutopilot } from "../api/autopilot";
import {
  createChannel,
  disconnectYoutube,
  getYoutubeStatus,
  listChannels,
  syncYoutubeChannel,
  YouTubeStatus,
} from "../api/channels";
import { AutopilotWizardModal } from "../components/AutopilotWizardModal";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";
import { Channel } from "../types";

const Channels = () => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [youtubeStatus, setYoutubeStatus] = useState<YouTubeStatus | null>(
    null,
  );
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newChannel, setNewChannel] = useState({ name: "", description: "" });
  const [runningAutopilotId, setRunningAutopilotId] = useState<string | null>(
    null,
  );
  const [wizardChannel, setWizardChannel] = useState<Channel | null>(null);

  const handleToggleAutopilot = async (channel: Channel) => {
    const nextState = !channel.autopilot_enabled;
    try {
      await toggleAutopilot(channel.id, nextState);
      toast.success(
        `Autopilot ${nextState ? "activated" : "paused"} for ${channel.name}`,
      );
      await loadData();
    } catch (err: any) {
      toast.error(
        err.response?.data?.detail?.message || "Failed to toggle autopilot",
      );
    }
  };

  const handleRunAutopilot = async (channel: Channel) => {
    setRunningAutopilotId(channel.id);
    const toastId = toast.loading(
      `Running full Autopilot cycle for ${channel.name}...`,
    );
    try {
      const res = await triggerAutopilot(channel.id);
      toast.success(`Autopilot completed! Generated: "${res.title}"`, {
        id: toastId,
      });
      await loadData();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail?.message ||
        err.message ||
        "Autopilot run failed";
      toast.error(`Autopilot error: ${msg}`, { id: toastId });
    } finally {
      setRunningAutopilotId(null);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [channelsData, ytStatus] = await Promise.all([
        listChannels(),
        getYoutubeStatus().catch(() => null),
      ]);
      setChannels(channelsData);
      setYoutubeStatus(ytStatus);
    } catch (error) {
      toast.error("Failed to load channels");
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const synced = await syncYoutubeChannel();
      toast.success(`Synced YouTube channel: ${synced.name}`);
      await loadData();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      const msg =
        typeof detail === "object"
          ? detail.message
          : detail || "Failed to sync YouTube channel";
      toast.error(msg);
      if (detail?.code === "YOUTUBE_INSUFFICIENT_SCOPES") {
        setYoutubeStatus((prev) =>
          prev
            ? {
                ...prev,
                status: "reauthorization_required",
                needs_reauthorization: true,
              }
            : null,
        );
      }
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    if (
      !window.confirm(
        "Are you sure you want to disconnect YouTube? You will need to re-authorize to publish.",
      )
    ) {
      return;
    }
    try {
      await disconnectYoutube();
      toast.success("YouTube disconnected");
      await loadData();
    } catch (error) {
      toast.error("Failed to disconnect YouTube");
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createChannel(newChannel);
      toast.success("Channel created successfully");
      setIsModalOpen(false);
      setNewChannel({ name: "", description: "" });
      loadData();
    } catch (error) {
      toast.error("Failed to create channel");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Channels</h1>
          <p className="text-sm text-slate-400">
            Manage your connected social accounts and YouTube channels
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {youtubeStatus?.status === "reauthorization_required" ? (
            <a
              href="/api/auth/google"
              className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Reconnect YouTube
            </a>
          ) : !youtubeStatus?.connected ? (
            <a
              href="/api/auth/google"
              className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
              </svg>
              Connect YouTube
            </a>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={handleSync}
                disabled={syncing}
                className="btn-secondary flex items-center gap-2 text-xs"
                title="Sync channel metadata from YouTube API"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 ${syncing ? "animate-spin" : ""}`}
                />
                {syncing ? "Syncing..." : "Sync YouTube"}
              </button>
              <button
                onClick={handleDisconnect}
                className="p-2 border border-slate-700 hover:border-red-600 hover:text-red-400 text-slate-400 rounded-lg transition-colors"
                title="Disconnect YouTube Account"
              >
                <Unlink className="w-4 h-4" />
              </button>
            </div>
          )}
          <button
            className="btn-secondary flex items-center gap-2"
            onClick={() => setIsModalOpen(true)}
          >
            <Plus className="w-4 h-4" />
            Manual Channel
          </button>
        </div>
      </div>

      {/* YouTube Status Banners */}
      {youtubeStatus?.status === "reauthorization_required" && (
        <div className="bg-amber-950/40 border border-amber-800/80 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <h4 className="text-sm font-semibold text-amber-200">
                YouTube Permissions Incomplete
              </h4>
              <p className="text-xs text-amber-300/80 mt-0.5">
                Your Google authorization is missing required channel inspection
                permissions (
                <code className="bg-amber-900/60 px-1 py-0.5 rounded text-amber-100">
                  youtube.readonly
                </code>
                ). Click Reconnect to update permissions.
              </p>
            </div>
          </div>
          <a
            href="/api/auth/google"
            className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg shadow whitespace-nowrap transition-colors"
          >
            Reconnect YouTube
          </a>
        </div>
      )}

      {youtubeStatus?.status === "connected" && (
        <div className="bg-emerald-950/30 border border-emerald-800/60 rounded-xl p-3 px-4 flex items-center justify-between text-xs text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>
              Google OAuth Connected with real YouTube scopes (
              <span className="text-emerald-200 font-medium">
                youtube.readonly, youtube.upload, yt-analytics
              </span>
              ).
            </span>
          </div>
          <span className="bg-emerald-900/50 text-emerald-300 px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider">
            Verified
          </span>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-400">
          Loading channels...
        </div>
      ) : channels.length === 0 ? (
        <Card>
          <EmptyState
            icon={Tv}
            title="No channels found"
            description="Connect your YouTube channel to start generating, automating, and publishing content."
            action={
              <div className="flex flex-col sm:flex-row gap-3 mt-4 justify-center">
                <a
                  href="/api/auth/google"
                  className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors"
                >
                  <svg
                    className="w-4 h-4"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                  </svg>
                  Connect YouTube Channel
                </a>
                <button
                  className="btn-secondary"
                  onClick={() => setIsModalOpen(true)}
                >
                  Create Manual Channel
                </button>
              </div>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {channels.map((channel) => (
            <Card key={channel.id} className="flex flex-col">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  {channel.thumbnail_url ? (
                    <img
                      src={channel.thumbnail_url}
                      alt={channel.name}
                      className="w-12 h-12 rounded-lg object-cover border border-slate-700"
                    />
                  ) : (
                    <div className="w-12 h-12 bg-indigo-500/20 text-indigo-400 rounded-lg flex items-center justify-center">
                      <Tv className="w-6 h-6" />
                    </div>
                  )}
                  <div>
                    <h3 className="text-lg font-semibold text-white leading-tight">
                      {channel.name}
                    </h3>
                    {channel.handle && (
                      <p className="text-xs text-slate-400">{channel.handle}</p>
                    )}
                  </div>
                </div>
                <StatusBadge status={channel.status} />
              </div>

              {channel.youtube_channel_id && (
                <div className="space-y-2 mb-4">
                  <div className="px-2.5 py-1 bg-red-950/40 border border-red-900/60 rounded text-[11px] text-red-300 font-mono flex items-center justify-between">
                    <span>YT ID: {channel.youtube_channel_id}</span>
                    <span className="text-red-400 font-sans font-medium">
                      Linked
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 py-2 px-3 bg-slate-900/60 rounded-lg border border-slate-800 text-center">
                    <div>
                      <div className="text-[10px] text-slate-400 uppercase tracking-wider">
                        Subs
                      </div>
                      <div className="text-xs font-semibold text-white">
                        {(channel.subscriber_count ?? 0).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-400 uppercase tracking-wider">
                        Videos
                      </div>
                      <div className="text-xs font-semibold text-white">
                        {(channel.video_count ?? 0).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-400 uppercase tracking-wider">
                        Views
                      </div>
                      <div className="text-xs font-semibold text-white">
                        {(channel.view_count ?? 0).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <p className="text-sm text-slate-300 mb-6 flex-1 line-clamp-2">
                {channel.description || "No description provided."}
              </p>

              <div className="pt-4 border-t border-slate-800 space-y-3">
                <div className="flex justify-between items-center text-sm">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleToggleAutopilot(channel)}
                      className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                        channel.autopilot_enabled
                          ? "bg-emerald-500"
                          : "bg-slate-700"
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          channel.autopilot_enabled
                            ? "translate-x-4"
                            : "translate-x-0"
                        }`}
                      />
                    </button>
                    <span className="text-xs font-medium text-slate-300">
                      Autopilot:{" "}
                      <span
                        className={
                          channel.autopilot_enabled
                            ? "text-emerald-400 font-semibold"
                            : "text-slate-500"
                        }
                      >
                        {channel.autopilot_enabled ? "Active" : "Paused"}
                      </span>
                    </span>
                  </div>

                  <span className="text-[11px] bg-slate-800/80 px-2 py-0.5 rounded text-slate-400 border border-slate-700">
                    Brain Ready
                  </span>
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setWizardChannel(channel)}
                    className="flex-1 btn-secondary text-xs py-2 flex items-center justify-center gap-1.5 border-blue-800/60 text-blue-300 hover:bg-blue-950/40"
                  >
                    <Sliders className="w-3.5 h-3.5 text-blue-400" />
                    Autopilot Wizard
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRunAutopilot(channel)}
                    disabled={runningAutopilotId === channel.id}
                    className="flex-1 btn-primary text-xs py-2 flex items-center justify-center gap-1.5"
                  >
                    <Zap
                      className={`w-3.5 h-3.5 ${runningAutopilotId === channel.id ? "animate-spin" : "text-amber-400"}`}
                    />
                    {runningAutopilotId === channel.id
                      ? "Running Cycle..."
                      : "Run Autopilot Cycle"}
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Add New Channel"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Channel Name
            </label>
            <input
              required
              type="text"
              className="input-field"
              value={newChannel.name}
              onChange={(e) =>
                setNewChannel({ ...newChannel, name: e.target.value })
              }
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Description
            </label>
            <textarea
              className="input-field min-h-[100px]"
              value={newChannel.description}
              onChange={(e) =>
                setNewChannel({ ...newChannel, description: e.target.value })
              }
            />
          </div>
          <div className="pt-4 flex justify-end gap-3">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setIsModalOpen(false)}
            >
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              Create Channel
            </button>
          </div>
        </form>
      </Modal>

      <AutopilotWizardModal
        isOpen={!!wizardChannel}
        onClose={() => setWizardChannel(null)}
        channel={wizardChannel}
        onConfigured={() => loadData()}
      />
    </div>
  );
};

export default Channels;
