import { client } from "./client";

export interface PublishingJob {
  id: string;
  video_id: string;
  channel_id?: string;
  platform: string;
  metadata: Record<string, any>;
  scheduled_at?: string;
  status: "pending" | "scheduled" | "published" | "failed";
  created_at: string;
}

export interface CalendarEvent {
  job_id: string;
  queue_item_id?: string;
  channel_id?: string;
  channel_name?: string;
  video_id?: string | null;
  title: string;
  topic?: string;
  status: string;
  current_stage?: string | null;
  display_status?: string;
  approval_status?: string;
  publish_status?: string;
  scheduled_at?: string;
  date: string;
  timezone?: string;
  platform: string;
  thumbnail_url?: string | null;
}

export const createPublishingJob = async (
  videoId: string,
  metadata: Record<string, any> = {},
  scheduledAt?: string,
) => {
  const res = await client.post<{ job_id: string; job: PublishingJob }>(
    "/publishing",
    {
      video_id: videoId,
      platform: "youtube",
      metadata,
      scheduled_at: scheduledAt || null,
    },
  );
  return res.data;
};

export const listPublishingJobs = async () => {
  const res = await client.get<PublishingJob[]>("/publishing");
  return res.data;
};

export const getPublishingCalendar = async () => {
  const res = await client.get<CalendarEvent[]>("/publishing/calendar");
  return res.data;
};

export const executePublish = async (jobId: string) => {
  const res = await client.post(`/publishing/${jobId}/publish`);
  return res.data;
};
