import React, { useEffect, useState } from 'react';
import Card from '../components/Card';
import StatusBadge from '../components/StatusBadge';
import { PlaySquare, Calendar, Clock } from 'lucide-react';
import { Video } from '../types';
import { listVideos } from '../api/videos';

const Videos = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);

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
          <div className="py-12 text-center text-slate-400">Loading videos...</div>
        ) : videos.length === 0 ? (
          <div className="py-12 text-center text-slate-400">No videos found. Create one!</div>
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
                  <tr key={video.id} className="hover:bg-slate-800/50 transition-colors">
                    <td className="py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-16 h-10 bg-slate-800 rounded flex items-center justify-center">
                          {video.thumbnail_path ? (
                            <img src={video.thumbnail_path} alt="thumbnail" className="w-full h-full object-cover rounded" />
                          ) : (
                            <PlaySquare className="w-5 h-5 text-slate-500" />
                          )}
                        </div>
                        <span className="font-medium text-white">{video.title}</span>
                      </div>
                    </td>
                    <td className="py-4">
                      <StatusBadge status={video.status} />
                    </td>
                    <td className="py-4 text-sm text-slate-300">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-slate-500" />
                        {video.duration ? `${video.duration}s` : '-'}
                      </div>
                    </td>
                    <td className="py-4 text-sm text-slate-300">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-slate-500" />
                        {new Date(video.created_at).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="py-4 text-right">
                      <button className="text-primary-400 hover:text-primary-300 text-sm font-medium">View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};

export default Videos;
