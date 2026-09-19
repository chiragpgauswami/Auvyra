import { Check, RefreshCw, Sparkles } from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  CaptionStyleConfig,
  CaptionStylePreset,
  getCaptionPresets,
  getChannelCaptionStyle,
  updateChannelCaptionStyle,
} from "../api/captionStyles";

interface CaptionStyleSelectorProps {
  channelId: string;
  onStyleSaved?: (savedConfig: CaptionStyleConfig) => void;
}

export const CaptionStyleSelector: React.FC<CaptionStyleSelectorProps> = ({
  channelId,
  onStyleSaved,
}) => {
  const [presets, setPresets] = useState<CaptionStylePreset[]>([]);
  const [currentConfig, setCurrentConfig] = useState<CaptionStyleConfig | null>(
    null,
  );
  const [selectedStyleId, setSelectedStyleId] = useState<string>("bold");
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);

  useEffect(() => {
    loadStyles();
  }, [channelId]);

  const loadStyles = async () => {
    setLoading(true);
    try {
      const [presetsData, activeConfig] = await Promise.all([
        getCaptionPresets(),
        getChannelCaptionStyle(channelId).catch(() => null),
      ]);
      setPresets(presetsData);
      if (activeConfig) {
        setCurrentConfig(activeConfig);
        setSelectedStyleId(activeConfig.style_id || "bold");
      }
    } catch (err: any) {
      toast.error("Failed to load caption styles");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPreset = (preset: CaptionStylePreset) => {
    setSelectedStyleId(preset.style_id);
    setCurrentConfig({
      ...preset.config,
      channel_id: channelId,
    });
  };

  const handleSave = async () => {
    if (!currentConfig) return;
    setSaving(true);
    try {
      const saved = await updateChannelCaptionStyle(channelId, currentConfig);
      setCurrentConfig(saved);
      toast.success(
        `Caption style '${saved.style_id.toUpperCase()}' active for channel!`,
      );
      if (onStyleSaved) {
        onStyleSaved(saved);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save caption style");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-slate-400">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" />
        Loading caption styles...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            Caption Typography & Aesthetic
          </h3>
          <p className="text-sm text-slate-400">
            Choose high-retention vertical Shorts typography. Snapshotted per
            production slot.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition shadow-lg shadow-blue-500/20"
        >
          {saving ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Check className="w-4 h-4" />
          )}
          Apply Style
        </button>
      </div>

      {/* Preset Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {presets.map((preset) => {
          const isSelected = selectedStyleId === preset.style_id;
          const cfg = preset.config;

          return (
            <div
              key={preset.style_id}
              onClick={() => handleSelectPreset(preset)}
              className={`cursor-pointer rounded-xl border p-4 transition duration-200 flex flex-col justify-between ${
                isSelected
                  ? "border-blue-500 bg-slate-800/90 ring-2 ring-blue-500/30"
                  : "border-slate-800 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-850"
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-white text-base flex items-center gap-2">
                    {preset.name}
                    {isSelected && (
                      <span className="bg-blue-500/20 text-blue-400 text-xs px-2 py-0.5 rounded-full border border-blue-500/30">
                        Active
                      </span>
                    )}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    {cfg.max_words_per_cue} words/cue
                  </span>
                </div>
                <p className="text-xs text-slate-400 mb-4">
                  {preset.description}
                </p>
              </div>

              {/* Visual Frame Simulation */}
              <div className="relative h-28 bg-gradient-to-b from-slate-950 to-slate-900 rounded-lg border border-slate-800/80 overflow-hidden flex items-center justify-center p-3">
                {/* Visual Safe Zone guide */}
                <div className="absolute inset-x-2 top-2 bottom-2 border border-dashed border-slate-700/40 rounded pointer-events-none" />

                {/* Styled Caption Pill / Box Simulation */}
                <div
                  className={`px-4 py-2 rounded-md text-center max-w-[90%] font-black uppercase tracking-wide shadow-md ${
                    cfg.background_type === "none"
                      ? "bg-transparent drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]"
                      : "border border-slate-800/50"
                  }`}
                  style={{
                    backgroundColor:
                      cfg.background_type === "none"
                        ? "transparent"
                        : `rgba(15, 23, 42, ${cfg.background_opacity})`,
                    color: cfg.text_color,
                    fontFamily:
                      cfg.font_family === "Courier"
                        ? "monospace"
                        : "sans-serif",
                    fontSize: "0.82rem",
                    letterSpacing: "0.05em",
                    textShadow:
                      cfg.stroke_color && cfg.outline_width > 0
                        ? `-1px -1px 0 ${cfg.stroke_color}, 1px -1px 0 ${cfg.stroke_color}, -1px 1px 0 ${cfg.stroke_color}, 1px 1px 0 ${cfg.stroke_color}`
                        : "none",
                  }}
                >
                  {preset.style_id === "highlight_word" ? (
                    <span>
                      ACTIVE WORD{" "}
                      <span style={{ color: cfg.highlight_color }}>
                        HIGHLIGHT
                      </span>
                    </span>
                  ) : (
                    preset.preview_sample
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CaptionStyleSelector;
