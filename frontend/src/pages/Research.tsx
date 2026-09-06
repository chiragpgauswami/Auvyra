import React, { useState } from 'react';
import Card from '../components/Card';
import { Search, Plus, Lightbulb } from 'lucide-react';
import toast from 'react-hot-toast';

const Research = () => {
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<string>('');

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    // Mock research functionality
    setTimeout(() => {
      setResults(`Research insights for "${topic}":\n\n1. Trending keywords: ...\n2. Competitor analysis: ...\n3. Suggested hooks: ...`);
      setLoading(false);
      toast.success('Research completed');
    }, 2000);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-white">Content Research</h1>
      
      <Card>
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-2.5 w-5 h-5 text-slate-500" />
            <input 
              type="text" 
              className="input-field pl-10" 
              placeholder="Enter a topic or niche to research..."
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              required
            />
          </div>
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Researching...' : 'Research'}
          </button>
        </form>
      </Card>

      {results && (
        <Card title="Research Insights">
          <div className="whitespace-pre-wrap text-slate-300 font-mono text-sm p-4 bg-slate-950 rounded-lg border border-slate-800">
            {results}
          </div>
          <div className="mt-4 flex justify-end">
            <button className="btn-secondary flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Save as Content Idea
            </button>
          </div>
        </Card>
      )}

      {!results && !loading && (
        <div className="py-12 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4">
            <Lightbulb className="w-8 h-8 text-slate-500" />
          </div>
          <p className="text-slate-400 max-w-sm">Enter a topic above to generate insights, trending keywords, and content suggestions.</p>
        </div>
      )}
    </div>
  );
};

export default Research;
