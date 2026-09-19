import client from "./client";

export interface CaptionStyleConfig {
  channel_id?: string;
  style_id: string;
  font_family: string;
  font_weight: string;
  font_size: number;
  text_color: string;
  highlight_color: string;
  stroke_color: string;
  outline_width: number;
  background_type: "pill" | "box" | "none";
  background_opacity: number;
  position: "safe_center" | "lower_third" | "upper_third";
  animation: string;
  word_grouping: string;
  max_words_per_cue: number;
  version?: number;
  updated_at?: string;
}

export interface CaptionStylePreset {
  style_id: string;
  name: string;
  description: string;
  preview_sample: string;
  config: CaptionStyleConfig;
}

export const getCaptionPresets = async (): Promise<CaptionStylePreset[]> => {
  const res = await client.get("/caption-styles/presets");
  return res.data;
};

export const getChannelCaptionStyle = async (
  channelId: string,
): Promise<CaptionStyleConfig> => {
  const res = await client.get(`/caption-styles/channels/${channelId}`);
  return res.data;
};

export const updateChannelCaptionStyle = async (
  channelId: string,
  config: CaptionStyleConfig,
): Promise<CaptionStyleConfig> => {
  const res = await client.put(`/caption-styles/channels/${channelId}`, config);
  return res.data;
};
