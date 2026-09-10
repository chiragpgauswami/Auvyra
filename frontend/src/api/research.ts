import { ResearchReport } from "../types";
import { client } from "./client";

export const createResearch = async (data: {
  channel_id: string;
  topic: string;
  channel_context?: Record<string, any>;
}) => {
  const response = await client.post<ResearchReport>("/research/", data);
  return response.data;
};

export const listResearch = async (channelId: string) => {
  const response = await client.get<ResearchReport[]>("/research/", {
    params: { channel_id: channelId },
  });
  return response.data;
};

export const getResearch = async (reportId: string) => {
  const response = await client.get<ResearchReport>(`/research/${reportId}`);
  return response.data;
};

export interface OpportunityItem {
  id?: string;
  report_id?: string;
  channel_id: string;
  topic: string;
  content_pillar?: string;
  why_now?: string;
  evidence?: string;
  content_gap?: string;
  recommended_angle?: string;
  target_audience?: string;
  hooks?: string[];
  sources?: string[];
  opportunity_score?: number;
  confidence?: number;
}

export const generateOpportunities = async (
  channelId: string,
  count: number = 4,
): Promise<OpportunityItem[]> => {
  const response = await client.post<OpportunityItem[]>(
    `/research/opportunities/${channelId}?count=${count}`,
  );
  return response.data;
};

export const listOpportunities = async (
  channelId: string,
): Promise<OpportunityItem[]> => {
  const response = await client.get<OpportunityItem[]>(
    `/research/opportunities/${channelId}`,
  );
  return response.data;
};
