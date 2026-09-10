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
