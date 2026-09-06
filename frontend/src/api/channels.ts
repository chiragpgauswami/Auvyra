import { client } from './client';
import { Channel } from '../types';

export const listChannels = async () => {
  const response = await client.get<Channel[]>('/channels/');
  return response.data;
};

export const createChannel = async (data: Partial<Channel>) => {
  const response = await client.post<Channel>('/channels/', data);
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
