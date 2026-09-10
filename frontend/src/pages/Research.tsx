import {
  ArrowRight,
  Flame,
  Lightbulb,
  Loader2,
  Search,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";
import { getChannelBrain, listChannels } from "../api/channels";
import { createContentIdea } from "../api/content";
import {
  createResearch,
  generateOpportunities,
  listOpportunities,
  OpportunityItem,
} from "../api/research";
import Card from "../components/Card";
import { Channel, ChannelBrain, ResearchReport } from "../types";

const Research = () => {
  const navigate = useNavigate();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>("");
  const [channelBrain, setChannelBrain] = useState<ChannelBrain | null>(null);

  // Opportunity Feed state
  const [opportunities, setOpportunities] = useState<OpportunityItem[]>([]);
  const [loadingOpps, setLoadingOpps] = useState(false);

  // Custom topic search state
  const [topic, setTopic] = useState("");
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [savingIdea, setSavingIdea] = useState(false);

  useEffect(() => {
    loadChannels();
  }, []);

  useEffect(() => {
    if (selectedChannelId) {
      loadChannelBrainAndOpps(selectedChannelId);
    }
  }, [selectedChannelId]);

  const loadChannels = async () => {
    try {
      const chs = await listChannels();
      setChannels(chs);
      if (chs.length > 0) {
        setSelectedChannelId(chs[0].id);
      }
    } catch (err) {
      console.error("Failed to load channels:", err);
    }
  };

  const loadChannelBrainAndOpps = async (channelId: string) => {
    try {
      const brain = await getChannelBrain(channelId).catch(() => null);
      setChannelBrain(brain);

      // Load existing opportunities
      const opps = await listOpportunities(channelId).catch(() => []);
      setOpportunities(opps);
    } catch (err) {
      console.error("Error loading brain/opps:", err);
    }
  };

  const handleGenerateOpps = async () => {
    if (!selectedChannelId) return;
    setLoadingOpps(true);
    try {
      const newOpps = await generateOpportunities(selectedChannelId, 4);
      setOpportunities(newOpps);
      toast.success(`Discovered ${newOpps.length} new content opportunities!`);
    } catch (err: any) {
      const msg =
        err.response?.data?.detail?.message ||
        err.message ||
        "Failed to generate opportunities";
      toast.error(`Error: ${msg}`);
    } finally {
      setLoadingOpps(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedChannelId) {
      toast.error("Please select a channel first.");
      return;
    }
    setLoadingSearch(true);
    setReport(null);
    try {
      const res = await createResearch({
        channel_id: selectedChannelId,
        topic,
      });
      setReport(res);
      toast.success("Research completed successfully!");
    } catch (err: any) {
      const msg =
        err.response?.data?.detail?.message || err.message || "Research failed";
      toast.error(`Research error: ${msg}`);
    } finally {
      setLoadingSearch(false);
    }
  };

  const handleCreateScript = (oppTopic: string) => {
    navigate(
      `/create?topic=${encodeURIComponent(oppTopic)}&channel_id=${selectedChannelId}`,
    );
  };

  const handleSaveIdea = async (oppTopic: string, description: string = "") => {
    if (!selectedChannelId) return;
    setSavingIdea(true);
    try {
      await createContentIdea({
        channel_id: selectedChannelId,
        title: oppTopic,
        description: description || `Research finding for ${oppTopic}`,
        keywords: [oppTopic],
      });
      toast.success("Saved as content idea!");
    } catch (err: any) {
      toast.error("Failed to save content idea");
    } finally {
      setSavingIdea(false);
    }
  };

  const selectedChannel = channels.find((c) => c.id === selectedChannelId);

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2.5">
            <Zap className="w-7 h-7 text-yellow-400" />
            Research & Opportunity Engine
          </h1>
          <p className="text-sm text-slate-400">
            Algorithmic opportunity discovery, audience search intent, and
            1-click script generation
          </p>
        </div>

        {channels.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Channel:</span>
            <select
              className="bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary-500"
              value={selectedChannelId}
              onChange={(e) => setSelectedChannelId(e.target.value)}
            >
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Channel Brain Positioning Context */}
      {channelBrain && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-3">
            <span className="px-2 py-0.5 rounded bg-primary-950 text-primary-300 border border-primary-800 font-semibold uppercase tracking-wider text-[10px]">
              Brain Active
            </span>
            <span className="text-slate-300">
              Niche:{" "}
              <strong className="text-white">{channelBrain.niche}</strong>
            </span>
            <span className="text-slate-400 hidden md:inline">|</span>
            <span className="text-slate-400 hidden md:inline truncate max-w-md">
              "{channelBrain.positioning}"
            </span>
          </div>
          <button
            onClick={() => navigate("/brain")}
            className="text-primary-400 hover:text-primary-300 font-medium whitespace-nowrap"
          >
            Edit Brain &rarr;
          </button>
        </div>
      )}

      {/* Section 1: AI Opportunity Feed */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary-400" />
            <h2 className="text-lg font-semibold text-white">
              AI Opportunity Feed
            </h2>
            <span className="bg-slate-800 text-slate-400 text-xs px-2 py-0.5 rounded-full">
              {opportunities.length} High-Yield Topics
            </span>
          </div>

          <button
            onClick={handleGenerateOpps}
            disabled={loadingOpps || !selectedChannelId}
            className="btn-primary flex items-center gap-2 text-xs"
          >
            {loadingOpps ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Scanning Algorithm...
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                Discover New Opportunities
              </>
            )}
          </button>
        </div>

        {loadingOpps ? (
          <div className="text-center py-16 bg-slate-900/40 border border-slate-800 rounded-xl">
            <Loader2 className="w-8 h-8 text-primary-400 animate-spin mx-auto mb-3" />
            <p className="text-sm font-semibold text-white">
              Analyzing YouTube Search Intent & Trends
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Grounded in {selectedChannel?.name || "Channel"} strategy...
            </p>
          </div>
        ) : opportunities.length === 0 ? (
          <div className="text-center py-12 bg-slate-900/40 border border-slate-800 rounded-xl">
            <Lightbulb className="w-8 h-8 text-slate-500 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-slate-300">
              No opportunities generated yet
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1 mb-4">
              Click "Discover New Opportunities" to analyze trending topics and
              gaps for this channel.
            </p>
            <button
              onClick={handleGenerateOpps}
              className="btn-secondary inline-flex items-center gap-2 text-xs"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Generate First Feed
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {opportunities.map((opp, idx) => (
              <div
                key={opp.id || idx}
                className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 flex flex-col justify-between transition-all"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-primary-950/60 text-primary-300 border border-primary-900/60">
                      {opp.content_pillar || "Core Pillar"}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-950/40 border border-emerald-900/50 px-2 py-0.5 rounded">
                      <Flame className="w-3 h-3 text-emerald-400" />
                      {Math.round(
                        opp.opportunity_score || (opp.confidence || 0.85) * 100,
                      )}
                      % Score
                    </span>
                  </div>

                  <h3 className="text-base font-semibold text-white leading-snug mb-3">
                    {opp.topic}
                  </h3>

                  <div className="space-y-2 text-xs text-slate-300 mb-4">
                    {opp.why_now && (
                      <p>
                        <strong className="text-slate-400">Why Now:</strong>{" "}
                        {opp.why_now}
                      </p>
                    )}
                    {opp.content_gap && (
                      <p>
                        <strong className="text-slate-400">Content Gap:</strong>{" "}
                        {opp.content_gap}
                      </p>
                    )}
                    {opp.recommended_angle && (
                      <p className="p-2 bg-slate-950/60 rounded border border-slate-800 text-slate-200">
                        <strong className="text-yellow-400">Angle:</strong>{" "}
                        {opp.recommended_angle}
                      </p>
                    )}
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                  <button
                    onClick={() =>
                      handleSaveIdea(opp.topic, opp.recommended_angle)
                    }
                    disabled={savingIdea}
                    className="text-xs text-slate-400 hover:text-white px-2.5 py-1 rounded transition-colors"
                  >
                    Save Idea
                  </button>

                  <button
                    onClick={() => handleCreateScript(opp.topic)}
                    className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5"
                  >
                    <span>Create Script</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Section 2: Deep Dive Topic Research Form */}
      <div className="pt-4 border-t border-slate-800">
        <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <Search className="w-5 h-5 text-slate-400" />
          Custom Topic Deep Dive
        </h2>

        <Card>
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-2.5 w-5 h-5 text-slate-500" />
                <input
                  type="text"
                  className="input-field pl-10"
                  placeholder="Enter custom topic to investigate (e.g. Why NVIDIA Blackwell changes everything)..."
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loadingSearch}
                className="btn-primary flex items-center gap-2"
              >
                {loadingSearch ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Researching...
                  </>
                ) : (
                  "Deep Dive"
                )}
              </button>
            </div>
          </form>

          {report && (
            <div className="mt-6 pt-6 border-t border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-white">
                  Research: {report.topic}
                </h3>
                <button
                  onClick={() => handleCreateScript(report.topic)}
                  className="btn-primary text-xs flex items-center gap-1.5"
                >
                  <span>Create Script</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {report.findings && report.findings.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {report.findings.map((f: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs text-slate-300"
                    >
                      <p className="font-semibold text-white mb-1">
                        {f.title || `Signal ${idx + 1}`}
                      </p>
                      <p>
                        {typeof f === "string"
                          ? f
                          : f.detail || f.description || JSON.stringify(f)}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {report.recommendations && report.recommendations.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-400 mb-2">
                    Recommended Hooks:
                  </h4>
                  <ul className="space-y-1.5">
                    {report.recommendations.map((rec: string, idx: number) => (
                      <li
                        key={idx}
                        className="text-xs text-slate-300 italic p-2 bg-slate-950/80 rounded border border-slate-800"
                      >
                        "{rec}"
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default Research;
