import { PipelineProgress, Video } from "../types";
import { client } from "./client";

export const listVideos = async (channelId?: string, status?: string) => {
  const response = await client.get<Video[]>("/videos/", {
    params: {
      ...(channelId ? { channel_id: channelId } : {}),
      ...(status ? { status } : {}),
    },
  });
  return response.data;
};

export const getVideo = async (id: string) => {
  const response = await client.get<Video>(`/videos/${id}`);
  return response.data;
};

export const generateVideo = async (data: any) => {
  const response = await client.post<{ job_id: string }>(
    "/videos/generate",
    data,
  );
  return response.data;
};

export const getVideoProgress = async (jobId: string) => {
  const response = await client.get<PipelineProgress>(
    `/jobs/${jobId}/progress`,
  );
  return response.data;
};
