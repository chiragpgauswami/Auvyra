import React, { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import Card from '../components/Card';
import StatusBadge from '../components/StatusBadge';
import { Video, Tv, Activity, Eye, PlaySquare } from 'lucide-react';
import { listVideos } from '../api/videos';
import { listChannels } from '../api/channels';
import { Link } from 'react-router-dom';

const Dashboard = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState({ videos: 0, channels: 0 });
  const [recentVideos, setRecentVideos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [videosData, channelsData] = await Promise.all([
          listVideos(),
          listChannels(),
        ]);
        setStats({ videos: videosData.length, channels: channelsData.length });
        setRecentVideos(videosData.slice(0, 5));
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Welcome back, {user?.name}</h1>
        <div className="flex gap-3">
          <Link to="/create" className="btn-primary flex items-center gap-2">
            <Video className="w-4 h-4" />
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
            <p className="text-2xl font-semibold text-white">{loading ? '-' : stats.videos}</p>
          </div>
        </Card>
        
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-emerald-500/10 rounded-lg">
            <Tv className="w-6 h-6 text-emerald-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Active Channels</p>
            <p className="text-2xl font-semibold text-white">{loading ? '-' : stats.channels}</p>
          </div>
        </Card>
        
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-amber-500/10 rounded-lg">
            <Activity className="w-6 h-6 text-amber-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Pending Jobs</p>
            <p className="text-2xl font-semibold text-white">-</p>
          </div>
        </Card>
        
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-purple-500/10 rounded-lg">
            <Eye className="w-6 h-6 text-purple-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Recent Views</p>
            <p className="text-2xl font-semibold text-white">-</p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Recent Videos" action={<Link to="/videos" className="text-sm text-primary-400 hover:text-primary-300">View all</Link>}>
          {recentVideos.length > 0 ? (
            <div className="divide-y divide-slate-800">
              {recentVideos.map(video => (
                <div key={video.id} className="py-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-slate-800 rounded flex items-center justify-center">
                      <PlaySquare className="w-5 h-5 text-slate-500" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{video.title}</p>
                      <p className="text-xs text-slate-400">{new Date(video.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                  <StatusBadge status={video.status} />
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-slate-400 text-sm">No recent videos</div>
          )}
        </Card>

        <Card title="Active Jobs">
          <div className="py-8 text-center text-slate-400 text-sm">No active jobs</div>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
