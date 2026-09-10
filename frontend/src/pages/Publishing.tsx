import { Calendar, Clock, Send, Video as VideoIcon } from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  CalendarEvent,
  createPublishingJob,
  executePublish,
  getPublishingCalendar,
} from "../api/publishing";
import { listVideos } from "../api/videos";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Video } from "../types";

const Publishing = () => {
  const [activeTab, setActiveTab] = useState<"ready" | "calendar">("ready");
  const [videos, setVideos] = useState<Video[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [scheduleDate, setScheduleDate] = useState<string>("");
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [vids, cal] = await Promise.all([
        listVideos(),
        getPublishingCalendar(),
      ]);
      setVideos(
        vids.filter(
          (v: Video) => v.status === "generated" || v.status === "ready",
        ),
      );
      setCalendarEvents(cal);
    } catch (err: any) {
      console.error("Failed to load publishing data:", err);
    } finally {
      setLoading(false);
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
      await fetchData();
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
      await fetchData();
    } catch (err: any) {
      toast.error(
        err.response?.data?.detail?.message || "Failed to schedule video",
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Publishing & Calendar
          </h1>
          <p className="text-slate-400">
            Deploy rendered content directly to your connected YouTube channel
            or schedule drops.
          </p>
        </div>

        <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-1">
          <button
            onClick={() => setActiveTab("ready")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === "ready"
                ? "bg-primary-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Ready to Publish ({videos.length})
          </button>
          <button
            onClick={() => setActiveTab("calendar")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === "calendar"
                ? "bg-primary-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Calendar & Queue ({calendarEvents.length})
          </button>
        </div>
      </div>

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
              {videos.map((vid) => (
                <Card key={vid.id} className="flex flex-col justify-between">
                  <div className="space-y-3">
                    <div className="aspect-[9/16] max-h-48 w-full bg-slate-950 rounded-md overflow-hidden relative border border-slate-800 flex items-center justify-center">
                      {vid.thumbnail_url || vid.thumbnail_path ? (
                        <img
                          src={
                            vid.thumbnail_url || vid.thumbnail_path || undefined
                          }
                          alt={vid.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <VideoIcon className="w-10 h-10 text-slate-700" />
                      )}
                      <div className="absolute top-2 right-2 bg-slate-900/80 px-2 py-0.5 rounded text-xs text-primary-400 font-medium">
                        {vid.duration ? `${vid.duration.toFixed(0)}s` : "9:16"}
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
              ))}
            </div>
          )}
        </div>
      ) : (
        <Card title="Scheduled Content Timeline">
          {calendarEvents.length === 0 ? (
            <EmptyState
              icon={Calendar}
              title="No upcoming scheduled content"
              description="Schedule a video from the 'Ready to Publish' tab to build out your channel deployment calendar."
            />
          ) : (
            <div className="divide-y divide-slate-800">
              {calendarEvents.map((evt) => (
                <div
                  key={evt.job_id}
                  className="py-4 flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center flex-shrink-0">
                      <Calendar className="w-5 h-5 text-primary-400" />
                    </div>
                    <div>
                      <h4 className="font-medium text-white text-sm">
                        {evt.title}
                      </h4>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {new Date(evt.date).toLocaleString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                        evt.status === "published"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : evt.status === "scheduled"
                            ? "bg-blue-500/10 text-blue-400 border-blue-500/20"
                            : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }`}
                    >
                      {evt.status.toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
};

export default Publishing;
