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
}

export interface Video {
  id: string;
  title: string;
  status: string;
  file_path: string | null;
  duration: number | null;
  thumbnail_path: string | null;
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
  id: string;
  title: string;
  description: string;
  status: string;
  keywords: string[];
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
