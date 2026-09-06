import { client } from './client';
import { Job } from '../types';

export const listJobs = async () => {
  const response = await client.get<Job[]>('/jobs/');
  return response.data;
};

export const getJobStatus = async (id: string) => {
  const response = await client.get<Job>(`/jobs/${id}`);
  return response.data;
};
