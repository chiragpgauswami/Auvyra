import {
  BookOpen,
  Brain as BrainIcon,
  CheckCircle,
  Clock,
  Flame,
  Lightbulb,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  getChannelBrain,
  listChannels,
  onboardChannel,
  rebuildChannelBrain,
} from "../api/channels";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import Modal from "../components/Modal";
import { Channel, ChannelBrain, ChannelOnboardingRequest } from "../types";

const Brain = () => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>("");
  const [brain, setBrain] = useState<ChannelBrain | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [rebuilding, setRebuilding] = useState<boolean>(false);
  const [isOnboardModalOpen, setIsOnboardModalOpen] = useState<boolean>(false);
  const [onboardingForm, setOnboardingForm] =
    useState<ChannelOnboardingRequest>({
      niche: "",
      target_audience: "",
      tone: "engaging",
      content_pillars: [],
      custom_instructions: "",
    });
  const [pillarsInput, setPillarsInput] = useState<string>("");

  useEffect(() => {
    loadChannels();
  }, []);

  useEffect(() => {
    if (selectedChannelId) {
      loadBrain(selectedChannelId);
    }
  }, [selectedChannelId]);

  const loadChannels = async () => {
    setLoading(true);
    try {
      const data = await listChannels();
      setChannels(data);
      if (data.length > 0) {
        setSelectedChannelId(data[0].id);
      }
    } catch (error) {
      toast.error("Failed to load channels");
    } finally {
      setLoading(false);
    }
  };

  const loadBrain = async (channelId: string) => {
    setLoading(true);
    try {
      const brainData = await getChannelBrain(channelId);
      setBrain(brainData);
    } catch (error: any) {
      setBrain(null);
    } finally {
      setLoading(false);
    }
  };

  const handleRebuild = async () => {
    if (!selectedChannelId) return;
    setRebuilding(true);
    try {
      const updated = await rebuildChannelBrain(selectedChannelId);
      setBrain(updated);
      toast.success(
        `Channel Brain updated to Strategy v${updated.strategy_version}`,
      );
    } catch (error: any) {
      toast.error("Failed to rebuild strategy");
    } finally {
      setRebuilding(false);
    }
  };

  const handleOnboard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedChannelId) return;
    const pillars = pillarsInput
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    const payload = { ...onboardingForm, content_pillars: pillars };

    setRebuilding(true);
    try {
      const newBrain = await onboardChannel(selectedChannelId, payload);
      setBrain(newBrain);
      setIsOnboardModalOpen(false);
      toast.success("Channel Brain onboarded and active!");
    } catch (error: any) {
      toast.error("Failed to onboard channel");
    } finally {
      setRebuilding(false);
    }
  };

  const selectedChannel = channels.find((c) => c.id === selectedChannelId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <BrainIcon className="w-7 h-7 text-primary-400" />
            Channel Brain
          </h1>
          <p className="text-sm text-slate-400">
            Durable channel intelligence, positioning strategy, hook rules, and
            learned algorithms
          </p>
        </div>

        <div className="flex items-center gap-3">
          {channels.length > 0 && (
            <select
              value={selectedChannelId}
              onChange={(e) => setSelectedChannelId(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
            >
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.name}
                </option>
              ))}
            </select>
          )}

          {brain && (
            <button
              onClick={handleRebuild}
              disabled={rebuilding}
              className="btn-secondary flex items-center gap-2 text-xs"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${rebuilding ? "animate-spin" : ""}`}
              />
              {rebuilding ? "Rebuilding..." : "Rebuild Strategy"}
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="text-center py-16 text-slate-400">
          Loading Channel Brain...
        </div>
      ) : !selectedChannel ? (
        <Card>
          <EmptyState
            icon={BrainIcon}
            title="No Channel Selected"
            description="Create or connect a YouTube channel to establish its Channel Brain."
          />
        </Card>
      ) : !brain ? (
        <Card className="text-center py-12">
          <div className="max-w-md mx-auto space-y-4">
            <div className="w-16 h-16 bg-primary-900/40 text-primary-400 rounded-2xl flex items-center justify-center mx-auto">
              <Sparkles className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-white">
              Initialize Channel Brain
            </h2>
            <p className="text-sm text-slate-400">
              {selectedChannel.name} has not been onboarded yet. Establish its
              strategic positioning, content pillars, and hook architecture.
            </p>
            <button
              onClick={() => {
                setOnboardingForm({
                  niche: selectedChannel.name,
                  target_audience:
                    "YouTube Shorts viewers looking for insightful content",
                  tone: "engaging",
                  content_pillars: [],
                  custom_instructions: "",
                });
                setPillarsInput(selectedChannel.name);
                setIsOnboardModalOpen(true);
              }}
              className="btn-primary inline-flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              Onboard Channel Brain
            </button>
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Strategy Version & Positioning Banner */}
          <div className="bg-gradient-to-r from-primary-950/40 via-slate-900 to-slate-900 border border-primary-800/40 rounded-xl p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2.5">
                <span className="px-2.5 py-0.5 rounded-full bg-primary-500/20 text-primary-300 text-xs font-semibold border border-primary-500/30">
                  Strategy Active v{brain.strategy_version}
                </span>
                <span className="text-xs text-slate-400">
                  Niche: <strong className="text-white">{brain.niche}</strong>
                </span>
                <span className="text-xs text-slate-400">
                  Tone:{" "}
                  <strong className="text-white capitalize">
                    {brain.tone}
                  </strong>
                </span>
              </div>
              <span className="text-xs text-slate-500">
                Audience: {brain.target_audience}
              </span>
            </div>
            <p className="text-sm text-slate-200 font-medium">
              "{brain.positioning}"
            </p>
          </div>

          {/* Grid: Content Pillars & Winning Hooks */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Content Pillars */}
            <Card>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <Target className="w-4 h-4 text-primary-400" />
                  Content Pillars
                </h3>
                <span className="text-xs text-slate-400">
                  {brain.content_pillars?.length || 0} Pillars
                </span>
              </div>
              <div className="space-y-3">
                {brain.content_pillars?.map((pillar, i) => (
                  <div
                    key={i}
                    className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 flex items-start justify-between"
                  >
                    <div>
                      <h4 className="text-sm font-semibold text-white">
                        {pillar.name}
                      </h4>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {pillar.description}
                      </p>
                    </div>
                    <span className="text-xs font-mono bg-slate-800 text-primary-300 px-2 py-0.5 rounded">
                      {Math.round((pillar.target_ratio || 0.25) * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </Card>

            {/* Winning Hooks */}
            <Card>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <Flame className="w-4 h-4 text-amber-400" />
                  High-Retention Hook Rules
                </h3>
                <span className="text-xs text-slate-400">
                  {brain.winning_hooks?.length || 0} Rules
                </span>
              </div>
              <div className="space-y-3">
                {brain.winning_hooks?.map((hook, i) => (
                  <div
                    key={i}
                    className="p-3 bg-slate-900/60 rounded-lg border border-slate-800"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-mono uppercase bg-amber-950/60 text-amber-300 px-2 py-0.5 rounded border border-amber-900/60">
                        {hook.hook_type}
                      </span>
                      <span className="text-xs text-emerald-400 font-semibold">
                        {Math.round((hook.effectiveness_score || 0.8) * 100)}%
                        Eff.
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 italic">
                      "{hook.pattern}"
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Grid: Title Patterns & Publishing Cadence */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Title Patterns */}
            <Card>
              <h3 className="text-base font-semibold text-white flex items-center gap-2 mb-4">
                <Lightbulb className="w-4 h-4 text-yellow-400" />
                Winning Title Patterns
              </h3>
              <div className="space-y-2">
                {brain.winning_title_patterns?.map((pattern, i) => (
                  <div
                    key={i}
                    className="p-2.5 bg-slate-900/60 rounded-lg border border-slate-800 text-xs text-slate-300 font-mono"
                  >
                    {pattern}
                  </div>
                ))}
              </div>
            </Card>

            {/* Learned Rules & Best Times */}
            <Card>
              <h3 className="text-base font-semibold text-white flex items-center gap-2 mb-4">
                <BookOpen className="w-4 h-4 text-emerald-400" />
                Autonomous Learned Rules
              </h3>
              <div className="space-y-2 mb-4">
                {brain.learned_rules?.map((rule, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-xs text-slate-300"
                  >
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{rule}</span>
                  </div>
                ))}
              </div>

              <div className="pt-4 border-t border-slate-800">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>Target Publishing Schedule</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {brain.best_publish_times?.map((t, i) => (
                    <span
                      key={i}
                      className="bg-slate-800 text-slate-300 px-2.5 py-1 rounded text-xs"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Onboarding Modal */}
      <Modal
        isOpen={isOnboardModalOpen}
        onClose={() => setIsOnboardModalOpen(false)}
        title="Onboard Channel Brain"
      >
        <form onSubmit={handleOnboard} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Channel Niche / Topic
            </label>
            <input
              required
              type="text"
              className="input-field"
              value={onboardingForm.niche}
              onChange={(e) =>
                setOnboardingForm({ ...onboardingForm, niche: e.target.value })
              }
              placeholder="e.g. Artificial Intelligence, Real Estate, History"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Target Audience
            </label>
            <input
              required
              type="text"
              className="input-field"
              value={onboardingForm.target_audience}
              onChange={(e) =>
                setOnboardingForm({
                  ...onboardingForm,
                  target_audience: e.target.value,
                })
              }
              placeholder="e.g. Tech professionals and curious learners aged 20-35"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Content Pillars (comma-separated)
            </label>
            <input
              type="text"
              className="input-field"
              value={pillarsInput}
              onChange={(e) => setPillarsInput(e.target.value)}
              placeholder="e.g. AI News, Robotics, Future Predictions, Coding"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Channel Tone
            </label>
            <select
              value={onboardingForm.tone}
              onChange={(e) =>
                setOnboardingForm({ ...onboardingForm, tone: e.target.value })
              }
              className="input-field"
            >
              <option value="engaging">Engaging & Fast-Paced</option>
              <option value="informative">Informative & Authoritative</option>
              <option value="entertaining">Entertaining & Humorous</option>
              <option value="provocative">
                Provocative & Thought-Provoking
              </option>
              <option value="dramatic">Dramatic & Cinematic</option>
            </select>
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setIsOnboardModalOpen(false)}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={rebuilding}
              className="btn-primary flex items-center gap-2"
            >
              {rebuilding ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              {rebuilding ? "Generating Strategy..." : "Generate Channel Brain"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Brain;
