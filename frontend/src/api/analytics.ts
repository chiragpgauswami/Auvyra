import { client } from "./client";

export interface AnalyticsSnapshot {
  id: string;
  channel_id: string;
  period: string;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  watch_time_hours: number;
  subscribers_gained: number;
  ctr: number;
  avg_view_duration: number;
  snapshot_date: string;
}

export interface StrategyInsight {
  id: string;
  channel_id: string;
  title: string;
  description: string;
  source: string;
  confidence: number;
  supporting_metrics: Record<string, any>;
  created_at: string;
}

export const getChannelAnalytics = async (channelId: string, period: string = "daily") => {
  const res = await client.get<AnalyticsSnapshot[]>(`/analytics/channel/${channelId}`, {
    params: { period }
  });
  return res.data;
};

export const syncChannelAnalytics = async (channelId: string, startDate?: string) => {
  const res = await client.post<{
    status: string;
    channel_id: string;
    synced_snapshots: number;
    total_views: number;
    total_watch_hours: number;
  }>(`/analytics/channel/${channelId}/sync`, {
    start_date: startDate || null
  });
  return res.data;
};

export const getChannelInsights = async (channelId: string) => {
  const res = await client.get<StrategyInsight[]>(`/analytics/insights/${channelId}`);
  return res.data;
};

export const generateChannelInsights = async (channelId: string) => {
  const res = await client.post<StrategyInsight[]>(`/analytics/insights/${channelId}/generate`);
  return res.data;
};
