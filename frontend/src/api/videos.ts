import { client } from './client';
import { Video, PipelineProgress, Job } from '../types';

export const listVideos = async () => {
  const response = await client.get<Video[]>('/videos/');
  return response.data;
};

export const getVideo = async (id: string) => {
  const response = await client.get<Video>(`/videos/${id}`);
  return response.data;
};

export const generateVideo = async (data: any) => {
  const response = await client.post<{ job_id: string }>('/videos/generate', data);
  return response.data;
};

export const getVideoProgress = async (jobId: string) => {
  const response = await client.get<PipelineProgress>(`/jobs/${jobId}/progress`);
  return response.data;
};
