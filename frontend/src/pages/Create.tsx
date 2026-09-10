import { PlaySquare, Sparkles, Wand2 } from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { useLocation } from "react-router-dom";
import { listChannels } from "../api/channels";
import { client } from "../api/client";
import { generateScript, rewriteScript } from "../api/content";
import { generateVideo } from "../api/videos";
import Card from "../components/Card";
import ProgressBar from "../components/ProgressBar";
import { usePolling } from "../hooks/usePolling";
import { Channel } from "../types";

const Create = () => {
  const location = useLocation();
  const [formData, setFormData] = useState({
    topic: "",
    script: "",
    aspect_ratio: "9:16",
    voice_name: "en-US-AriaNeural-Female",
  });

  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [isGeneratingScript, setIsGeneratingScript] = useState(false);
  const [isRewritingScript, setIsRewritingScript] = useState(false);
  const [currentScriptId, setCurrentScriptId] = useState<string | null>(null);

  useEffect(() => {
    if (location.state) {
      const state = location.state as { topic?: string; script?: string };
      setFormData((prev) => ({
        ...prev,
        topic: state.topic || prev.topic,
        script: state.script || prev.script,
      }));
    }
  }, [location.state]);

  useEffect(() => {
    const fetchChannels = async () => {
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
    fetchChannels();
  }, []);

  const handleGenerateScript = async () => {
    if (!formData.topic.trim()) {
      toast.error("Please provide a topic first");
      return;
    }
    if (!selectedChannelId) {
      toast.error("Please select a target channel");
      return;
    }
    setIsGeneratingScript(true);
    try {
      const result = await generateScript(selectedChannelId, formData.topic);
      const text = result.script_text || result.final_script || "";
      setFormData((prev) => ({ ...prev, script: text }));
      if (result.id) {
        setCurrentScriptId(result.id);
      }
      toast.success("Structured script generated with channel hook rules!");
    } catch (err: any) {
      toast.error(
        err.response?.data?.detail?.message || "Failed to generate script",
      );
    } finally {
      setIsGeneratingScript(false);
    }
  };

  const handleRewriteScript = async (instruction: string) => {
    if (!formData.script.trim()) {
      toast.error("No script text to rewrite");
      return;
    }
    setIsRewritingScript(true);
    try {
      if (currentScriptId) {
        const res = await rewriteScript(currentScriptId, instruction);
        setFormData((prev) => ({ ...prev, script: res.script_text }));
        toast.success(`Rewritten: ${instruction} (v${res.version})`);
      } else {
        // Fallback if not saved as script yet
        toast("Generating a fresh script with selected tone...");
        const res = await generateScript(
          selectedChannelId,
          `${formData.topic} (${instruction})`,
        );
        setFormData((prev) => ({ ...prev, script: res.script_text }));
        if (res.id) setCurrentScriptId(res.id);
        toast.success("Script updated!");
      }
    } catch (err: any) {
      toast.error(
        err.response?.data?.detail?.message || "Failed to rewrite script",
      );
    } finally {
      setIsRewritingScript(false);
    }
  };

  const fetchProgress = async () => {
    if (!jobId) return null;
    try {
      const res = await client.get(`/jobs/${jobId}/progress`);
      return res.data;
    } catch (e) {
      return null;
    }
  };

  const { data: progress } = usePolling(fetchProgress, 2000, !!jobId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.topic && !formData.script) {
      toast.error("Please provide a topic or a script");
      return;
    }
    if (!selectedChannelId) {
      toast.error("Please select or create a channel first");
      return;
    }
    try {
      const res = await generateVideo({
        channel_id: selectedChannelId,
        request_data: formData,
      });
      setJobId(res.job_id);
      toast.success("Video generation started!");
    } catch (error: any) {
      const msg =
        error.response?.data?.detail?.message ||
        error.message ||
        "Failed to start generation";
      toast.error(`Generation error: ${msg}`);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white mb-2">Create New Video</h1>
        <p className="text-slate-400">
          Generate a professional video using AI from just a topic or script.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card title="Video Details">
            <form onSubmit={handleSubmit} className="space-y-6">
              {channels.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Target Channel
                  </label>
                  <select
                    className="input-field bg-slate-900"
                    value={selectedChannelId}
                    onChange={(e) => setSelectedChannelId(e.target.value)}
                  >
                    {channels.map((ch) => (
                      <option key={ch.id} value={ch.id}>
                        {ch.name} ({ch.handle || ch.status})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Topic (Optional if Script provided)
                  </label>
                  {formData.topic.trim() && (
                    <button
                      type="button"
                      onClick={handleGenerateScript}
                      disabled={isGeneratingScript}
                      className="text-xs flex items-center gap-1 text-primary-400 hover:text-primary-300 transition-colors font-medium bg-primary-500/10 px-2 py-1 rounded border border-primary-500/20"
                    >
                      <Sparkles
                        className={`w-3.5 h-3.5 ${isGeneratingScript ? "animate-spin" : ""}`}
                      />
                      {isGeneratingScript
                        ? "Generating..."
                        : "Generate AI Script"}
                    </button>
                  )}
                </div>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g., The history of ancient Rome in 60 seconds"
                  value={formData.topic}
                  onChange={(e) =>
                    setFormData({ ...formData, topic: e.target.value })
                  }
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-slate-300">
                    Script (Optional, AI will generate if empty)
                  </label>
                  {formData.script.trim() && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs text-slate-400">Rewrite:</span>
                      <button
                        type="button"
                        onClick={() =>
                          handleRewriteScript(
                            "Make it punchier and faster-paced",
                          )
                        }
                        disabled={isRewritingScript}
                        className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded border border-slate-700 transition-colors"
                      >
                        ⚡ Punchier
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          handleRewriteScript(
                            "Make the opening hook more controversial and curious",
                          )
                        }
                        disabled={isRewritingScript}
                        className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded border border-slate-700 transition-colors"
                      >
                        🎣 Viral Hook
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          handleRewriteScript(
                            "Shorten by 25% for higher retention",
                          )
                        }
                        disabled={isRewritingScript}
                        className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded border border-slate-700 transition-colors"
                      >
                        ⏱️ Shorter
                      </button>
                    </div>
                  )}
                </div>
                <textarea
                  className="input-field min-h-[150px]"
                  placeholder="Enter your exact script here..."
                  value={formData.script}
                  onChange={(e) =>
                    setFormData({ ...formData, script: e.target.value })
                  }
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Aspect Ratio
                  </label>
                  <select
                    className="input-field bg-slate-900"
                    value={formData.aspect_ratio}
                    onChange={(e) =>
                      setFormData({ ...formData, aspect_ratio: e.target.value })
                    }
                  >
                    <option value="9:16">9:16 (Shorts/Reels)</option>
                    <option value="16:9">16:9 (YouTube)</option>
                    <option value="1:1">1:1 (Instagram)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Voice
                  </label>
                  <select
                    className="input-field bg-slate-900"
                    value={formData.voice_name}
                    onChange={(e) =>
                      setFormData({ ...formData, voice_name: e.target.value })
                    }
                  >
                    <option value="en-US-AriaNeural-Female">
                      Aria (Female, Natural)
                    </option>
                    <option value="en-US-GuyNeural-Male">
                      Guy (Male, Professional)
                    </option>
                    <option value="en-US-JennyNeural-Female">
                      Jenny (Female, Friendly)
                    </option>
                    <option value="en-US-ChristopherNeural-Male">
                      Christopher (Male, Authoritative)
                    </option>
                  </select>
                </div>
              </div>

              <div className="pt-4 flex justify-end">
                <button
                  type="submit"
                  disabled={!!jobId && progress?.percent !== 100}
                  className="btn-primary flex items-center gap-2"
                >
                  <Wand2 className="w-4 h-4" />
                  Generate Video
                </button>
              </div>
            </form>
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Status">
            {jobId ? (
              <div className="space-y-4">
                <ProgressBar
                  progress={progress?.percent || 0}
                  stage={progress?.stage || "Initializing..."}
                />
                <p className="text-sm text-slate-400">
                  {progress?.message || "Preparing pipeline"}
                </p>

                {progress?.percent === 100 && (
                  <div className="mt-6 p-4 bg-slate-900 border border-emerald-500/30 rounded-lg text-center space-y-4">
                    <div className="flex items-center justify-center gap-2 text-emerald-400 font-semibold">
                      <PlaySquare className="w-5 h-5" />
                      <span>Video Generated Successfully!</span>
                    </div>

                    {/* Browser Video Preview */}
                    <div className="overflow-hidden rounded-lg border border-slate-800 bg-black flex items-center justify-center">
                      <video
                        controls
                        playsInline
                        className="w-full max-h-[380px] object-contain rounded-lg"
                        src={
                          progress.result?.video_id
                            ? `/api/videos/${progress.result.video_id}/stream${localStorage.getItem("access_token") ? `?token=${encodeURIComponent(localStorage.getItem("access_token") || "")}` : ""}`
                            : progress.result?.stream_url || ""
                        }
                      >
                        Your browser does not support HTML5 video preview.
                      </video>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-2 pt-2">
                      <a
                        href={
                          progress.result?.video_id
                            ? `/api/videos/${progress.result.video_id}/download${localStorage.getItem("access_token") ? `?token=${encodeURIComponent(localStorage.getItem("access_token") || "")}` : ""}`
                            : "#"
                        }
                        download
                        className="btn-secondary text-xs flex-1 flex items-center justify-center gap-1.5 py-2"
                      >
                        Download MP4
                      </a>
                      <a
                        href="/publishing"
                        className="btn-primary text-xs flex-1 flex items-center justify-center gap-1.5 py-2"
                      >
                        Publish to YouTube
                      </a>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500 text-sm">
                Submit the form to start generation.
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Create;
