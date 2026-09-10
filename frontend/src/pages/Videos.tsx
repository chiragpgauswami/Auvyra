import { Calendar, Clock, Download, PlaySquare, Share2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { listVideos } from "../api/videos";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";
import { Video } from "../types";

const Videos = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const data = await listVideos();
        setVideos(data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    fetchVideos();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">Videos</h1>
      </div>

      <Card>
        {loading ? (
          <div className="py-12 text-center text-slate-400">
            Loading videos...
          </div>
        ) : videos.length === 0 ? (
          <div className="py-12 text-center text-slate-400">
            No videos found. Create one!
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
                {videos.map((video) => (
                  <tr
                    key={video.id}
                    className="hover:bg-slate-800/50 transition-colors"
                  >
                    <td className="py-4">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-16 h-10 bg-slate-800 rounded flex items-center justify-center cursor-pointer"
                          onClick={() => setSelectedVideo(video)}
                        >
                          {video.thumbnail_path ? (
                            <img
                              src={video.thumbnail_path}
                              alt="thumbnail"
                              className="w-full h-full object-cover rounded"
                            />
                          ) : (
                            <PlaySquare className="w-5 h-5 text-slate-500" />
                          )}
                        </div>
                        <span
                          className="font-medium text-white cursor-pointer hover:text-primary-400 transition-colors"
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
                        {video.duration ? `${video.duration.toFixed(1)}s` : "-"}
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
                ))}
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
