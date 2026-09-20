import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  Clock,
  Filter,
  RefreshCw,
  Send,
  Sparkles,
  Video as VideoIcon,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { approveQueueSlot } from "../api/autopilot";
import { listChannels } from "../api/channels";
import {
  CalendarEvent,
  createPublishingJob,
  executePublish,
  getPublishingCalendar,
} from "../api/publishing";
import { listVideos } from "../api/videos";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Channel, Video } from "../types";
import { getThumbnailUrl } from "../utils/media";

const Publishing = () => {
  const [activeTab, setActiveTab] = useState<"ready" | "calendar">("ready");
  const [videos, setVideos] = useState<Video[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [scheduleDate, setScheduleDate] = useState<string>("");
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);

  // Filters for Calendar
  const [selectedChannelId, setSelectedChannelId] = useState<string>("");
  const [calendarView, setCalendarView] = useState<
    "upcoming" | "today" | "this_week" | "all"
  >("upcoming");

  const fetchData = async (isRefresh: boolean = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    try {
      const [vids, cal, chs] = await Promise.all([
        listVideos(),
        getPublishingCalendar(),
        listChannels().catch(() => []),
      ]);
      setVideos(
        vids.filter(
          (v: Video) => v.status === "generated" || v.status === "ready",
        ),
      );
      setCalendarEvents(cal);
      setChannels(chs);
    } catch (err: any) {
      console.error("Failed to load publishing data:", err);
      toast.error("Failed to load publishing calendar data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleInstantPublish = async (video: Video) => {
    setPublishingId(video.id);
    try {
      const jobRes = await createPublishingJob(video.id, {
        title: video.title,
        description: video.description || "",
        tags: video.tags || [],
        privacy: "public",
      });
      await executePublish(jobRes.job_id);
      toast.success("Successfully published to YouTube!");
      await fetchData(true);
    } catch (err: any) {
      const msg =
        err.response?.data?.detail?.message ||
        err.message ||
        "Publishing failed";
      toast.error(`Publishing blocked: ${msg}`);
    } finally {
      setPublishingId(null);
    }
  };

  const handleScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVideoId || !scheduleDate) {
      toast.error("Please select a date and time to schedule");
      return;
    }
    try {
      const vid = videos.find((v) => v.id === selectedVideoId);
      await createPublishingJob(
        selectedVideoId,
        {
          title: vid?.title || "Scheduled Video",
          privacy: "public",
        },
        new Date(scheduleDate).toISOString(),
      );
      toast.success("Video successfully scheduled on publishing calendar!");
      setSelectedVideoId(null);
      setScheduleDate("");
      setActiveTab("calendar");
      await fetchData(true);
    } catch (err: any) {
      toast.error(
        err.response?.data?.detail?.message || "Failed to schedule video",
      );
    }
  };

  const handleApprove = async (slotId: string) => {
    setApprovingId(slotId);
    try {
      await approveQueueSlot(slotId);
      toast.success("Video approved! Added to YouTube upload queue.");
      await fetchData(true);
    } catch (err: any) {
      const msg =
        err.response?.data?.detail?.message ||
        err.message ||
        "Failed to approve slot";
      toast.error(`Approval failed: ${msg}`);
    } finally {
      setApprovingId(null);
    }
  };

  // Filter calendar events
  const filteredCalendarEvents = useMemo(() => {
    return calendarEvents.filter((evt) => {
      // Channel filter
      if (selectedChannelId && evt.channel_id !== selectedChannelId) {
        return false;
      }

      const evtDate = new Date(evt.scheduled_at || evt.date);
      const now = new Date();

      if (calendarView === "today") {
        return evtDate.toDateString() === now.toDateString();
      }

      if (calendarView === "this_week") {
        const weekStart = new Date(now);
        weekStart.setHours(0, 0, 0, 0);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 7);
        return evtDate >= weekStart && evtDate <= weekEnd;
      }

      if (calendarView === "upcoming") {
        // Show upcoming dates OR items still active/pending upload
        return (
          evtDate >= now ||
          evt.display_status === "Scheduled for Upload" ||
          evt.display_status === "Awaiting Approval" ||
          evt.display_status === "Generating" ||
          evt.display_status === "Scheduled — Video not generated"
        );
      }

      // "all"
      return true;
    });
  }, [calendarEvents, selectedChannelId, calendarView]);

  const getStatusBadge = (evt: CalendarEvent) => {
    const status = evt.display_status || evt.status;
    switch (status) {
      case "Published":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            Published
          </span>
        );
      case "Scheduled for Upload":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
            Scheduled for Upload
          </span>
        );
      case "Awaiting Approval":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <AlertCircle className="w-3 h-3 text-amber-400" />
            Awaiting Approval
          </span>
        );
      case "Generating":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/30">
            <Sparkles className="w-3 h-3 text-purple-400 animate-spin" />
            Generating {evt.current_stage ? `(${evt.current_stage})` : ""}
          </span>
        );
      case "Failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
            {evt.display_status || evt.status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            Publishing & Calendar
          </h1>
          <p className="text-slate-400 text-sm">
            Deploy rendered content directly to your connected YouTube channel
            or review scheduled autopilot drops.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing || loading}
            title="Refresh schedule"
            className="p-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={`w-4 h-4 ${refreshing ? "animate-spin text-primary-400" : ""}`}
            />
          </button>

          <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-1">
            <button
              onClick={() => setActiveTab("ready")}
              className={`px-4 py-1.5 text-xs sm:text-sm font-medium rounded-md transition-colors ${
                activeTab === "ready"
                  ? "bg-primary-600 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Ready to Publish ({videos.length})
            </button>
            <button
              onClick={() => setActiveTab("calendar")}
              className={`px-4 py-1.5 text-xs sm:text-sm font-medium rounded-md transition-colors ${
                activeTab === "calendar"
                  ? "bg-primary-600 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Calendar & Queue ({calendarEvents.length})
            </button>
          </div>
        </div>
      </div>

      {/* Ready to Publish Tab */}
      {activeTab === "ready" ? (
        <div className="space-y-6">
          {videos.length === 0 ? (
            <Card>
              <EmptyState
                icon={Send}
                title="No videos currently waiting for deployment"
                description="Create or generate a video first. Once rendered, you can 1-click publish or schedule here."
              />
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {videos.map((vid) => {
                const thumbSrc = getThumbnailUrl(
                  vid.thumbnail_url,
                  vid.thumbnail_path,
                  vid.id,
                );

                return (
                  <Card key={vid.id} className="flex flex-col justify-between">
                    <div className="space-y-3">
                      <div className="aspect-[9/16] max-h-48 w-full bg-slate-950 rounded-md overflow-hidden relative border border-slate-800 flex items-center justify-center">
                        {thumbSrc ? (
                          <img
                            src={thumbSrc}
                            alt={vid.title}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <VideoIcon className="w-10 h-10 text-slate-700" />
                        )}
                        <div className="absolute top-2 right-2 bg-slate-900/80 px-2 py-0.5 rounded text-xs text-primary-400 font-medium">
                          {vid.duration
                            ? `${vid.duration.toFixed(0)}s`
                            : "9:16"}
                        </div>
                      </div>
                      <div>
                        <h3 className="font-semibold text-white line-clamp-1">
                          {vid.title}
                        </h3>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                          {vid.description ||
                            "Generated high-retention vertical short."}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-800/80 flex gap-2">
                      <button
                        onClick={() => handleInstantPublish(vid)}
                        disabled={publishingId === vid.id}
                        className="btn-primary flex-1 text-xs py-2 flex items-center justify-center gap-1.5"
                      >
                        <Send className="w-3.5 h-3.5" />
                        {publishingId === vid.id
                          ? "Publishing..."
                          : "Publish Now"}
                      </button>
                      <button
                        onClick={() =>
                          setSelectedVideoId(
                            selectedVideoId === vid.id ? null : vid.id,
                          )
                        }
                        className="btn-secondary text-xs py-2 px-3 flex items-center gap-1"
                      >
                        <Clock className="w-3.5 h-3.5" />
                        Schedule
                      </button>
                    </div>

                    {selectedVideoId === vid.id && (
                      <form
                        onSubmit={handleScheduleSubmit}
                        className="mt-3 p-3 bg-slate-900/80 border border-slate-800 rounded-md space-y-2"
                      >
                        <label className="text-xs text-slate-300 block font-medium">
                          Select Publish Time
                        </label>
                        <input
                          type="datetime-local"
                          value={scheduleDate}
                          onChange={(e) => setScheduleDate(e.target.value)}
                          className="input-field text-xs py-1.5 bg-slate-950"
                          required
                        />
                        <div className="flex justify-end gap-2 pt-1">
                          <button
                            type="button"
                            onClick={() => setSelectedVideoId(null)}
                            className="text-xs text-slate-400 hover:text-white px-2 py-1"
                          >
                            Cancel
                          </button>
                          <button
                            type="submit"
                            className="btn-primary text-xs py-1 px-3"
                          >
                            Confirm Schedule
                          </button>
                        </div>
                      </form>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        /* Calendar & Queue Tab */
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
            {/* View Tabs */}
            <div className="flex flex-wrap gap-1">
              {(
                [
                  { id: "upcoming", label: "Upcoming" },
                  { id: "today", label: "Today" },
                  { id: "this_week", label: "This Week" },
                  { id: "all", label: "All Slots" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setCalendarView(tab.id)}
                  className={`px-3 py-1 text-xs font-medium rounded-lg transition-colors ${
                    calendarView === tab.id
                      ? "bg-primary-600 text-white"
                      : "text-slate-400 hover:text-white hover:bg-slate-800"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Channel Dropdown Filter */}
            {channels.length > 0 && (
              <div className="flex items-center gap-2">
                <Filter className="w-3.5 h-3.5 text-slate-500" />
                <select
                  value={selectedChannelId}
                  onChange={(e) => setSelectedChannelId(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="">All Connected Channels</option>
                  {channels.map((ch) => (
                    <option key={ch.id} value={ch.id}>
                      {ch.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <Card title="Scheduled Content Timeline & Autopilot Queue">
            {filteredCalendarEvents.length === 0 ? (
              <EmptyState
                icon={Calendar}
                title="No scheduled content matches current filter"
                description="Configure Autopilot in Channel Control Center or schedule a video from 'Ready to Publish'."
              />
            ) : (
              <div className="divide-y divide-slate-800">
                {filteredCalendarEvents.map((evt) => {
                  const targetSlotId = evt.queue_item_id || evt.job_id;
                  const isAwaitingApproval =
                    evt.display_status === "Awaiting Approval" ||
                    evt.status === "ready_for_approval" ||
                    evt.approval_status === "ready_for_approval";

                  const thumbSrc = getThumbnailUrl(
                    evt.thumbnail_url,
                    null,
                    evt.video_id,
                  );

                  return (
                    <div
                      key={evt.job_id}
                      className="py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-850/40 rounded-lg px-2 transition-colors"
                    >
                      {/* Left: Thumbnail & Details */}
                      <div className="flex items-center gap-3">
                        <div className="w-14 h-14 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center flex-shrink-0 overflow-hidden">
                          {thumbSrc ? (
                            <img
                              src={thumbSrc}
                              alt={evt.title}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <Calendar className="w-6 h-6 text-primary-400/80" />
                          )}
                        </div>

                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="font-semibold text-white text-sm">
                              {evt.title}
                            </h4>
                            {evt.channel_name && (
                              <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-primary-300 border border-slate-700/70">
                                {evt.channel_name}
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-3 text-xs text-slate-400">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5 text-slate-500" />
                              {new Date(
                                evt.scheduled_at || evt.date,
                              ).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                year: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                            {evt.timezone && (
                              <span className="text-slate-500 font-mono text-[10px]">
                                ({evt.timezone})
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Right: Status badge & Actions */}
                      <div className="flex items-center gap-3 self-end md:self-center flex-wrap">
                        {getStatusBadge(evt)}

                        {isAwaitingApproval && (
                          <button
                            onClick={() => handleApprove(targetSlotId)}
                            disabled={approvingId === targetSlotId}
                            className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5 shadow-sm"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            {approvingId === targetSlotId
                              ? "Approving..."
                              : "Approve & Upload"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};

export default Publishing;
