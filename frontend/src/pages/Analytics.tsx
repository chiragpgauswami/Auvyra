import React, { useEffect, useState } from "react";
import { BarChart2, TrendingUp, Users, Eye, RefreshCw, Clock, Sparkles, AlertCircle } from "lucide-react";
import toast from "react-hot-toast";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { listChannels } from "../api/channels";
import { getChannelAnalytics, syncChannelAnalytics, getChannelInsights, AnalyticsSnapshot, StrategyInsight } from "../api/analytics";
import { Channel } from "../types";

const Analytics = () => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>("");
  const [snapshots, setSnapshots] = useState<AnalyticsSnapshot[]>([]);
  const [insights, setInsights] = useState<StrategyInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    const initChannels = async () => {
      try {
        const chs = await listChannels();
        setChannels(chs);
        if (chs.length > 0) {
          setSelectedChannelId(chs[0].id);
        }
      } catch (err) {
        console.error("Failed to load channels:", err);
      }
    };
    initChannels();
  }, []);

  const loadChannelData = async (channelId: string) => {
    if (!channelId) return;
    setLoading(true);
    try {
      const [snaps, ins] = await Promise.all([
        getChannelAnalytics(channelId),
        getChannelInsights(channelId)
      ]);
      setSnapshots(snaps);
      setInsights(ins);
    } catch (err) {
      console.error("Failed to load analytics data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedChannelId) {
      loadChannelData(selectedChannelId);
    }
  }, [selectedChannelId]);

  const handleSyncAnalytics = async () => {
    if (!selectedChannelId) return;
    setSyncing(true);
    try {
      const res = await syncChannelAnalytics(selectedChannelId);
      toast.success(`Synced ${res.synced_snapshots} snapshots (${res.total_views} views)!`);
      await loadChannelData(selectedChannelId);
    } catch (err: any) {
      const msg = err.response?.data?.detail?.message || err.message || "Failed to sync YouTube Analytics";
      toast.error(`Sync blocked: ${msg}`);
    } finally {
      setSyncing(false);
    }
  };

  const totalViews = snapshots.reduce((acc, s) => acc + s.views, 0);
  const totalWatchHours = snapshots.reduce((acc, s) => acc + s.watch_time_hours, 0);
  const totalSubs = snapshots.reduce((acc, s) => acc + s.subscribers_gained, 0);
  const avgAvd = snapshots.length > 0 ? (snapshots.reduce((acc, s) => acc + s.avg_view_duration, 0) / snapshots.length) : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Channel Analytics & Performance</h1>
          <p className="text-slate-400">
            Real performance telemetry ingested directly from YouTube Analytics API v2.
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          {channels.length > 0 && (
            <select
              value={selectedChannelId}
              onChange={(e) => setSelectedChannelId(e.target.value)}
              className="input-field bg-slate-900 text-sm py-2"
            >
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.name} ({ch.handle || (ch.youtube_channel_id ? "Connected" : "Unconnected")})
                </option>
              ))}
            </select>
          )}

          <button
            onClick={handleSyncAnalytics}
            disabled={syncing || !selectedChannelId}
            className="btn-primary flex items-center gap-2 text-sm whitespace-nowrap"
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Syncing..." : "Sync Analytics"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-blue-500/10 rounded-lg">
            <Eye className="w-6 h-6 text-blue-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Total Views</p>
            <p className="text-2xl font-semibold text-white">{totalViews.toLocaleString()}</p>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="p-3 bg-indigo-500/10 rounded-lg">
            <Clock className="w-6 h-6 text-indigo-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Watch Time (Hours)</p>
            <p className="text-2xl font-semibold text-white">{totalWatchHours.toFixed(1)}</p>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="p-3 bg-pink-500/10 rounded-lg">
            <Users className="w-6 h-6 text-pink-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Subscribers Gained</p>
            <p className="text-2xl font-semibold text-white">+{totalSubs.toLocaleString()}</p>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="p-3 bg-emerald-500/10 rounded-lg">
            <TrendingUp className="w-6 h-6 text-emerald-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Avg. View Duration</p>
            <p className="text-2xl font-semibold text-white">{avgAvd.toFixed(1)}s</p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card title="Telemetry Timeline">
            {snapshots.length === 0 ? (
              <div className="h-64 flex items-center justify-center border border-dashed border-slate-700 rounded-lg bg-slate-900/50">
                <div className="text-center text-slate-500 flex flex-col items-center p-6">
                  <BarChart2 className="w-8 h-8 mb-2 text-slate-600" />
                  <p className="font-medium text-slate-400">No Analytics Snapshots Ingested</p>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm">
                    Click "Sync Analytics" above to ingest live telemetry from your connected YouTube account.
                  </p>
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="text-xs uppercase bg-slate-800/60 text-slate-400">
                    <tr>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3">Views</th>
                      <th className="px-4 py-3">Watch Time</th>
                      <th className="px-4 py-3">Avg Duration</th>
                      <th className="px-4 py-3">Likes / Shares</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {snapshots.slice(0, 10).map((s) => (
                      <tr key={s.id} className="hover:bg-slate-800/30">
                        <td className="px-4 py-3 font-medium text-white">
                          {new Date(s.snapshot_date).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3">{s.views.toLocaleString()}</td>
                        <td className="px-4 py-3">{s.watch_time_hours.toFixed(1)}h</td>
                        <td className="px-4 py-3">{s.avg_view_duration.toFixed(1)}s</td>
                        <td className="px-4 py-3">
                          {s.likes} 👍 / {s.shares} ↗️
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div>
          <Card title="Strategic Intelligence">
            {insights.length === 0 ? (
              <div className="text-center p-6 text-slate-500 flex flex-col items-center">
                <Sparkles className="w-8 h-8 mb-2 text-slate-600" />
                <p className="text-xs text-slate-400">Insights generate automatically after analytics sync.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {insights.map((ins) => (
                  <div key={ins.id} className="p-3 bg-slate-900/90 rounded-lg border border-slate-800 space-y-1">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-semibold text-primary-400 uppercase tracking-wider">{ins.title}</h4>
                      <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">
                        {(ins.confidence * 100).toFixed(0)}% conf
                      </span>
                    </div>
                    <p className="text-xs text-slate-300">{ins.description}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
