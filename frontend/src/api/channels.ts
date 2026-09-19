import { Channel } from "../types";
import { client } from "./client";

export const listChannels = async () => {
  const response = await client.get<Channel[]>("/channels/");
  return response.data;
};

export const createChannel = async (data: Partial<Channel>) => {
  const response = await client.post<Channel>("/channels/", data);
  return response.data;
};

export const getChannel = async (id: string) => {
  const response = await client.get<Channel>(`/channels/${id}`);
  return response.data;
};

export const updateChannel = async (id: string, data: Partial<Channel>) => {
  const response = await client.put<Channel>(`/channels/${id}`, data);
  return response.data;
};

export const deleteChannel = async (id: string) => {
  const response = await client.delete(`/channels/${id}`);
  return response.data;
};

export interface YouTubeStatus {
  connected: boolean;
  status:
    | "not_connected"
    | "connected"
    | "reauthorization_required"
    | "no_channel";
  granted_scopes?: string[];
  missing_scopes?: string[];
  needs_reauthorization?: boolean;
  channel?: Partial<Channel>;
  message?: string;
}

export const getYoutubeStatus = async (): Promise<YouTubeStatus> => {
  const response = await client.get<YouTubeStatus>("/channels/youtube/status");
  return response.data;
};

export const syncYoutubeChannel = async () => {
  const response = await client.post<Channel>("/channels/youtube/sync");
  return response.data;
};

export const disconnectYoutube = async () => {
  const response = await client.delete("/channels/youtube/disconnect");
  return response.data;
};

import { ChannelBrain, ChannelOnboardingRequest } from "../types";

export const onboardChannel = async (
  channelId: string,
  data: ChannelOnboardingRequest,
): Promise<ChannelBrain> => {
  const response = await client.post<ChannelBrain>(
    `/channels/${channelId}/onboard`,
    data,
  );
  return response.data;
};

export const getChannelBrain = async (
  channelId: string,
): Promise<ChannelBrain> => {
  const response = await client.get<ChannelBrain>(
    `/channels/${channelId}/brain`,
  );
  return response.data;
};

export const rebuildChannelBrain = async (
  channelId: string,
): Promise<ChannelBrain> => {
  const response = await client.post<ChannelBrain>(
    `/channels/${channelId}/brain/rebuild`,
  );
  return response.data;
};

export interface NicheRecommendation {
  id: string;
  name: string;
  description: string;
  market_demand: string;
  competition_level: string;
  opportunity_score: number;
  target_audience: string;
  suggested_pillars: string[];
  recommended_format: string;
  style_sample: string;
  source: string;
  confidence: number;
}

export interface AutopilotConfigPayload {
  mode: "off" | "assisted" | "full_autopilot";
  format: "shorts" | "longform";
  niche: string;
  custom_niche?: string | null;
  target_audience?: string;
  tone?: string;
  language?: string;
  target_geography?: string;
  content_pillars?: string[];
  schedule: {
    frequency_per_week: number;
    timezone: string;
    days_of_week: number[];
    times: string[];
  };
  approval_required?: boolean;
  privacy_status?: "private" | "unlisted" | "public";
  tags?: string[];
}

export const getAutopilotNiches = async (
  channelId: string,
  refresh: boolean = false,
): Promise<NicheRecommendation[]> => {
  const response = await client.get<NicheRecommendation[]>(
    `/channels/${channelId}/autopilot/niches?refresh=${refresh}`,
  );
  return response.data;
};

export const configureAutopilot = async (
  channelId: string,
  config: AutopilotConfigPayload,
): Promise<any> => {
  const response = await client.post(
    `/channels/${channelId}/autopilot/configure`,
    config,
  );
  return response.data;
};

export const getAutopilotConfig = async (channelId: string): Promise<any> => {
  const response = await client.get(`/channels/${channelId}/autopilot/config`);
  return response.data;
};

export const getAutopilotQueue = async (
  channelId: string,
  status?: string,
): Promise<any[]> => {
  const query = status ? `?status=${status}` : "";
  const response = await client.get<any[]>(
    `/channels/${channelId}/autopilot/queue${query}`,
  );
  return response.data;
};
