import React, { useState } from 'react';
import Card from '../components/Card';
import ProgressBar from '../components/ProgressBar';
import { generateVideo } from '../api/videos';
import { usePolling } from '../hooks/usePolling';
import { client } from '../api/client';
import toast from 'react-hot-toast';
import { Wand2, PlaySquare } from 'lucide-react';

const Create = () => {
  const [formData, setFormData] = useState({
    topic: '',
    script: '',
    aspect_ratio: '9:16',
    voice: 'alloy',
  });
  
  const [jobId, setJobId] = useState<string | null>(null);
  
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
      toast.error('Please provide a topic or a script');
      return;
    }
    try {
      const res = await generateVideo(formData);
      setJobId(res.job_id);
      toast.success('Video generation started!');
    } catch (error) {
      toast.error('Failed to start generation');
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white mb-2">Create New Video</h1>
        <p className="text-slate-400">Generate a professional video using AI from just a topic or script.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card title="Video Details">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Topic (Optional if Script provided)</label>
                <input 
                  type="text" 
                  className="input-field" 
                  placeholder="e.g., The history of ancient Rome in 60 seconds"
                  value={formData.topic}
                  onChange={(e) => setFormData({ ...formData, topic: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Script (Optional, AI will generate if empty)</label>
                <textarea 
                  className="input-field min-h-[150px]" 
                  placeholder="Enter your exact script here..."
                  value={formData.script}
                  onChange={(e) => setFormData({ ...formData, script: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Aspect Ratio</label>
                  <select 
                    className="input-field bg-slate-900"
                    value={formData.aspect_ratio}
                    onChange={(e) => setFormData({ ...formData, aspect_ratio: e.target.value })}
                  >
                    <option value="9:16">9:16 (Shorts/Reels)</option>
                    <option value="16:9">16:9 (YouTube)</option>
                    <option value="1:1">1:1 (Instagram)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Voice</label>
                  <select 
                    className="input-field bg-slate-900"
                    value={formData.voice}
                    onChange={(e) => setFormData({ ...formData, voice: e.target.value })}
                  >
                    <option value="alloy">Alloy (Neutral)</option>
                    <option value="echo">Echo (Male)</option>
                    <option value="nova">Nova (Female)</option>
                  </select>
                </div>
              </div>

              <div className="pt-4 flex justify-end">
                <button type="submit" disabled={!!jobId && progress?.percent !== 100} className="btn-primary flex items-center gap-2">
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
                <ProgressBar progress={progress?.percent || 0} stage={progress?.stage || 'Initializing...'} />
                <p className="text-sm text-slate-400">{progress?.message || 'Preparing pipeline'}</p>
                
                {progress?.percent === 100 && (
                  <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-center">
                    <PlaySquare className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                    <p className="text-emerald-400 font-medium">Video Complete!</p>
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
