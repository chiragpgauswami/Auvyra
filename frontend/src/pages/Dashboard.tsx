import {
  Activity,
  Brain,
  Eye,
  Lightbulb,
  PlaySquare,
  Tv,
  Video,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listChannels } from "../api/channels";
import { listJobs } from "../api/jobs";
import { listVideos } from "../api/videos";
import { useAuth } from "../auth/AuthContext";
import Card from "../components/Card";
import ProgressBar from "../components/ProgressBar";
import StatusBadge from "../components/StatusBadge";
import { Channel, Job, Video as VideoType } from "../types";
import { getThumbnailUrl } from "../utils/media";

const Dashboard = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState({
    videos: 0,
    channels: 0,
    pendingJobs: 0,
    totalViews: 0,
  });
  const [recentVideos, setRecentVideos] = useState<VideoType[]>([]);
  const [activeJobs, setActiveJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [videosData, channelsData, jobsData] = await Promise.all([
          listVideos().catch(() => []),
          listChannels().catch(() => []),
          listJobs().catch(() => []),
        ]);

        const pending = jobsData.filter(
          (j: Job) => j.status === "queued" || j.status === "processing",
        ).length;
        const views = channelsData.reduce(
          (acc: number, ch: Channel) => acc + (ch.view_count || 0),
          0,
        );

        setStats({
          videos: videosData.length,
          channels: channelsData.length,
          pendingJobs: pending,
          totalViews: views,
        });
        setRecentVideos(videosData.slice(0, 5));
        setActiveJobs(jobsData.slice(0, 5));
      } catch (error) {
        console.error("Dashboard error:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Welcome back, {user?.name}
          </h1>
          <p className="text-slate-400 text-sm">
            Auvyra Autonomous YouTube Operating System
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/brain"
            className="btn-secondary flex items-center gap-1.5 text-xs py-2"
          >
            <Brain className="w-3.5 h-3.5 text-primary-400" />
            AI Brain
          </Link>
          <Link
            to="/research"
            className="btn-secondary flex items-center gap-1.5 text-xs py-2"
          >
            <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
            Opportunities
          </Link>
          <Link
            to="/create"
            className="btn-primary flex items-center gap-1.5 text-xs py-2"
          >
            <Video className="w-3.5 h-3.5" />
            Create Video
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-primary-500/10 rounded-lg">
            <Video className="w-6 h-6 text-primary-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Total Videos</p>
            <p className="text-2xl font-semibold text-white">
              {loading ? "-" : stats.videos}
            </p>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="p-3 bg-emerald-500/10 rounded-lg">
            <Tv className="w-6 h-6 text-emerald-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">
              Active Channels
            </p>
            <p className="text-2xl font-semibold text-white">
              {loading ? "-" : stats.channels}
            </p>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="p-3 bg-amber-500/10 rounded-lg">
            <Activity className="w-6 h-6 text-amber-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Pending Jobs</p>
            <p className="text-2xl font-semibold text-white">
              {loading ? "-" : stats.pendingJobs}
            </p>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="p-3 bg-purple-500/10 rounded-lg">
            <Eye className="w-6 h-6 text-purple-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Channel Views</p>
            <p className="text-2xl font-semibold text-white">
              {loading ? "-" : stats.totalViews.toLocaleString()}
            </p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Recent Videos"
          action={
            <Link
              to="/videos"
              className="text-xs text-primary-400 hover:text-primary-300 font-medium"
            >
              View all
            </Link>
          }
        >
          {recentVideos.length > 0 ? (
            <div className="divide-y divide-slate-800">
              {recentVideos.map((video) => (
                <div
                  key={video.id}
                  className="py-3 flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-slate-800 rounded flex items-center justify-center overflow-hidden flex-shrink-0">
                      {getThumbnailUrl(video.thumbnail_url, video.thumbnail_path, video.id) ? (
                        <img
                          src={
                            getThumbnailUrl(
                              video.thumbnail_url,
                              video.thumbnail_path,
                              video.id
                            ) || undefined
                          }
                          alt={video.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <PlaySquare className="w-5 h-5 text-slate-500" />
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white line-clamp-1">
                        {video.title}
                      </p>
                      <p className="text-xs text-slate-400">
                        {new Date(video.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <StatusBadge status={video.status} />
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-slate-400 text-sm">
              No recent videos generated yet.
            </div>
          )}
        </Card>

        <Card
          title="Background Engine Jobs"
          action={
            <Link
              to="/publishing"
              className="text-xs text-primary-400 hover:text-primary-300 font-medium"
            >
              Publishing queue
            </Link>
          }
        >
          {activeJobs.length > 0 ? (
            <div className="divide-y divide-slate-800">
              {activeJobs.map((job) => (
                <div key={job.id} className="py-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-white capitalize">
                      {job.type.replace("_", " ")}
                    </p>
                    <StatusBadge status={job.status} />
                  </div>
                  {job.status === "processing" && (
                    <ProgressBar
                      progress={job.progress}
                      stage="Processing..."
                    />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-slate-400 text-sm">
              All background workers idle.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
