import { client } from './client';
import { ContentIdea } from '../types';

export const listContentIdeas = async () => {
  const response = await client.get<ContentIdea[]>('/content/ideas');
  return response.data;
};

export const createContentIdea = async (data: Partial<ContentIdea>) => {
  const response = await client.post<ContentIdea>('/content/ideas', data);
  return response.data;
};

export const updateContentIdeaStatus = async (id: string, status: string) => {
  const response = await client.put<ContentIdea>(`/content/ideas/${id}/status`, { status });
  return response.data;
};
