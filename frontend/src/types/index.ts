export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  email_verified: boolean;
}

export interface Channel {
  id: string;
  user_id: string;
  name: string;
  handle: string | null;
  description: string;
  status: string;
  autopilot_enabled: boolean;
  youtube_channel_id?: string | null;
  thumbnail_url?: string | null;
  subscriber_count?: number;
  video_count?: number;
  view_count?: number;
}

export interface Video {
  id: string;
  title: string;
  description?: string;
  status: string;
  file_path: string | null;
  duration: number | null;
  thumbnail_path: string | null;
  thumbnail_url?: string | null;
  tags?: string[];
  youtube_video_id?: string | null;
  youtube_url?: string | null;
  created_at: string;
}

export interface Job {
  id: string;
  type: string;
  status: string;
  progress: number;
  error: string | null;
  created_at: string;
}

export interface ContentIdea {
  id?: string;
  channel_id?: string;
  title: string;
  description: string;
  status?: string;
  keywords: string[];
}

export interface ResearchReport {
  id: string;
  topic: string;
  channel_id: string;
  findings: Array<{ title?: string; description?: string } | string>;
  recommendations: string[];
  sources: string[];
  created_at?: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface PipelineProgress {
  stage: string;
  percent: number;
  message: string;
}

export interface HookRule {
  hook_type: string;
  pattern: string;
  effectiveness_score: number;
}

export interface ContentPillar {
  name: string;
  description: string;
  target_ratio: number;
}

export interface ChannelBrain {
  id: string;
  user_id: string;
  channel_id: string;
  niche: string;
  target_audience: string;
  language: string;
  geography: string;
  tone: string;
  positioning: string;
  content_pillars: ContentPillar[];
  winning_topics: string[];
  losing_topics: string[];
  winning_hooks: HookRule[];
  losing_hooks: string[];
  winning_title_patterns: string[];
  best_publish_times: string[];
  learned_rules: string[];
  strategy_version: number;
  created_at: string;
  updated_at: string;
}

export interface ChannelOnboardingRequest {
  niche: string;
  target_audience: string;
  tone?: string;
  content_pillars?: string[];
  language?: string;
  target_geography?: string;
  reference_channels?: string[];
  custom_instructions?: string;
}
