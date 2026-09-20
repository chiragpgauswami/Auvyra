import { Calendar, Clock, Download, PlaySquare, Plus, Share2, Video as VideoIcon, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listChannels } from "../api/channels";
import { listVideos } from "../api/videos";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";
import { Channel, Video } from "../types";
import { getThumbnailUrl } from "../utils/media";

const Videos = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);

  useEffect(() => {
    listChannels().then(setChannels).catch(console.error);
  }, []);

  const fetchVideos = async () => {
    setLoading(true);
    try {
      const filterStatus = statusFilter === "all" ? undefined : statusFilter;
      const chId = selectedChannelId || undefined;
      const data = await listVideos(chId, filterStatus);
      setVideos(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVideos();
  }, [selectedChannelId, statusFilter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Videos</h1>
          <p className="text-slate-400 text-sm">
            All manual and autonomous videos generated for your channels.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {channels.length > 0 && (
            <select
              value={selectedChannelId}
              onChange={(e) => setSelectedChannelId(e.target.value)}
              className="bg-slate-900 border border-slate-800 text-sm text-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary-500"
            >
              <option value="">All Channels</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.name}
                </option>
              ))}
            </select>
          )}

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-sm text-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            <option value="all">All Statuses</option>
            <option value="generated">Ready / Generated</option>
            <option value="generating">Generating</option>
            <option value="queued">Queued</option>
            <option value="published">Published</option>
            <option value="failed">Failed</option>
          </select>

          <button
            onClick={fetchVideos}
            className="btn-secondary text-xs py-1.5 px-3"
          >
            Refresh
          </button>

          <Link
            to="/create"
            className="btn-primary text-xs py-1.5 px-3.5 flex items-center gap-1.5 font-medium shadow-md shadow-primary-500/20"
          >
            <Plus className="w-4 h-4" />
            Create Video
          </Link>
        </div>
      </div>

      <Card>
        {loading ? (
          <div className="py-12 text-center text-slate-400">
            Loading videos...
          </div>
        ) : videos.length === 0 ? (
          <div className="py-16 text-center text-slate-400 space-y-4">
            <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
              <VideoIcon className="w-6 h-6" />
            </div>
            <div>
              <p className="text-white font-medium">No videos found</p>
              <p className="text-xs text-slate-500 mt-1">Get started by creating your first high-retention video.</p>
            </div>
            <Link
              to="/create"
              className="btn-primary text-xs py-2 px-4 inline-flex items-center gap-2 font-medium"
            >
              <Plus className="w-4 h-4" />
              Create Video
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-800 text-sm text-slate-400">
                  <th className="pb-3 font-medium">Video</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Duration</th>
                  <th className="pb-3 font-medium">Created Date</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {videos.map((video) => {
                  const thumbSrc = getThumbnailUrl(
                    video.thumbnail_url,
                    video.thumbnail_path,
                    video.id,
                  );

                  return (
                    <tr
                      key={video.id}
                      className="hover:bg-slate-800/50 transition-colors"
                    >
                      <td className="py-4">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-16 h-10 bg-slate-800 rounded flex items-center justify-center cursor-pointer overflow-hidden border border-slate-700/50"
                            onClick={() => setSelectedVideo(video)}
                          >
                            {thumbSrc ? (
                              <img
                                src={thumbSrc}
                                alt="thumbnail"
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <PlaySquare className="w-5 h-5 text-slate-500" />
                            )}
                          </div>
                          <span
                            className="font-medium text-white cursor-pointer hover:text-primary-400 transition-colors line-clamp-1 max-w-[280px]"
                            onClick={() => setSelectedVideo(video)}
                          >
                            {video.title}
                          </span>
                        </div>
                      </td>
                      <td className="py-4">
                        <StatusBadge status={video.status} />
                      </td>
                      <td className="py-4 text-sm text-slate-300">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-slate-500" />
                          {video.duration
                            ? `${video.duration.toFixed(1)}s`
                            : "-"}
                        </div>
                      </td>
                      <td className="py-4 text-sm text-slate-300">
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-slate-500" />
                          {new Date(video.created_at).toLocaleDateString()}
                        </div>
                      </td>
                      <td className="py-4 text-right">
                        <button
                          onClick={() => setSelectedVideo(video)}
                          className="text-primary-400 hover:text-primary-300 text-sm font-medium"
                        >
                          View & Play
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Video Playback Modal */}
      {selectedVideo && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full overflow-hidden shadow-2xl space-y-4 p-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold text-white truncate max-w-[85%]">
                {selectedVideo.title}
              </h3>
              <button
                onClick={() => setSelectedVideo(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="aspect-[9/16] max-h-[460px] bg-black rounded-lg overflow-hidden flex items-center justify-center mx-auto border border-slate-800">
              <video
                controls
                autoPlay
                playsInline
                className="w-full h-full object-contain"
                src={`/api/videos/${selectedVideo.id}/stream${localStorage.getItem("access_token") ? `?token=${encodeURIComponent(localStorage.getItem("access_token") || "")}` : ""}`}
              >
                Browser does not support video playback.
              </video>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
              <span>
                Status:{" "}
                <strong className="text-emerald-400 uppercase">
                  {selectedVideo.status}
                </strong>
              </span>
              <span>
                Duration:{" "}
                {selectedVideo.duration
                  ? `${selectedVideo.duration.toFixed(1)}s`
                  : "N/A"}
              </span>
            </div>

            <div className="flex gap-2 pt-2">
              <a
                href={`/api/videos/${selectedVideo.id}/download${localStorage.getItem("access_token") ? `?token=${encodeURIComponent(localStorage.getItem("access_token") || "")}` : ""}`}
                download
                className="btn-secondary text-xs flex-1 flex items-center justify-center gap-1.5 py-2"
              >
                <Download className="w-4 h-4" /> Download MP4
              </a>
              <a
                href="/publishing"
                className="btn-primary text-xs flex-1 flex items-center justify-center gap-1.5 py-2"
              >
                <Share2 className="w-4 h-4" /> Publish to YouTube
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Videos;
