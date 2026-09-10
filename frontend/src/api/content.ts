import { ContentIdea } from "../types";
import { client } from "./client";

export const listContentIdeas = async (channelId?: string) => {
  const response = await client.get<ContentIdea[]>("/content/ideas", {
    params: channelId ? { channel_id: channelId } : undefined,
  });
  return response.data;
};

export const createContentIdea = async (data: Partial<ContentIdea>) => {
  const response = await client.post<ContentIdea>("/content/ideas", data);
  return response.data;
};

export const updateContentIdeaStatus = async (id: string, status: string) => {
  const response = await client.put<ContentIdea>(
    `/content/ideas/${id}/status`,
    { status },
  );
  return response.data;
};

export const generateScript = async (
  channelId: string,
  topic: string,
  duration: number = 45,
) => {
  const response = await client.post("/content/scripts/generate", {
    channel_id: channelId,
    topic,
    duration,
  });
  return response.data;
};

export const rewriteScript = async (scriptId: string, instruction: string) => {
  const response = await client.post(`/content/scripts/${scriptId}/rewrite`, {
    instruction,
  });
  return response.data;
};
