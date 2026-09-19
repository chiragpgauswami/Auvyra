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
  approvalRequired: boolean = true,
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
  const res = await client.get<AutopilotStatus>(
    `/autopilot/${channelId}/status`,
  );
  return res.data;
};

export interface AutopilotObservability {
  channel_id: string;
  channel_name: string;
  autopilot_enabled: boolean;
  mode: string;
  queue_depth: Record<string, number>;
  active_worker_leases: Array<{
    slot_id: string;
    stage: string;
    worker_id: string;
    lease_expires_at: string | null;
  }>;
  last_successful_upload: {
    published_at: string | null;
    video_id: string | null;
    youtube_url: string | null;
  } | null;
  last_learning_run: {
    completed_at: string | null;
    status: string | null;
    signals_count: number;
  } | null;
  recent_events: Array<{
    id?: string;
    stage: string;
    status: string;
    progress: number;
    message: string;
    timestamp: string;
    error?: any;
  }>;
  recent_failures: Array<{
    slot_id: string;
    topic: string;
    current_stage: string;
    attempts: number;
    last_error: any;
  }>;
}

export const getAutopilotObservability = async (
  channelId: string,
): Promise<AutopilotObservability> => {
  const res = await client.get<AutopilotObservability>(
    `/autopilot/${channelId}/observability`,
  );
  return res.data;
};

export const getChannelEvents = async (
  channelId: string,
  limit: number = 30,
) => {
  const res = await client.get(`/autopilot/${channelId}/events`, {
    params: { limit },
  });
  return res.data;
};

export const approveQueueSlot = async (slotId: string) => {
  const res = await client.post(`/autopilot/queue/${slotId}/approve`);
  return res.data;
};

export const retryQueueSlot = async (slotId: string) => {
  const res = await client.post(`/autopilot/queue/${slotId}/retry`);
  return res.data;
};

export const cancelQueueSlot = async (slotId: string) => {
  const res = await client.delete(`/autopilot/queue/${slotId}`);
  return res.data;
};

export const triggerSchedulerTick = async () => {
  const res = await client.post("/autopilot/scheduler/tick");
  return res.data;
};
