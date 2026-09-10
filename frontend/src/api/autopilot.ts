import { client } from "./client";

export interface AutopilotStatus {
  channel_id: string;
  name: string;
  autopilot_enabled: boolean;
  approval_required: boolean;
  strategy_version: number;
  niche: string;
}

export const toggleAutopilot = async (
  channelId: string,
  enabled: boolean,
  approvalRequired: boolean = true
) => {
  const res = await client.post(`/autopilot/${channelId}/toggle`, {
    enabled,
    approval_required: approvalRequired,
  });
  return res.data;
};

export const triggerAutopilot = async (channelId: string) => {
  const res = await client.post(`/autopilot/${channelId}/trigger`);
  return res.data;
};

export const getAutopilotStatus = async (channelId: string) => {
  const res = await client.get<AutopilotStatus>(`/autopilot/${channelId}/status`);
  return res.data;
};
