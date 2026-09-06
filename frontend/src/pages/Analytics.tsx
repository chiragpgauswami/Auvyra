import React from 'react';
import Card from '../components/Card';
import { BarChart2, TrendingUp, Users, Eye } from 'lucide-react';

const Analytics = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Analytics Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-blue-500/10 rounded-lg">
            <Eye className="w-6 h-6 text-blue-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Total Views</p>
            <p className="text-2xl font-semibold text-white">0</p>
          </div>
        </Card>
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-pink-500/10 rounded-lg">
            <Users className="w-6 h-6 text-pink-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Subscribers Gained</p>
            <p className="text-2xl font-semibold text-white">0</p>
          </div>
        </Card>
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-emerald-500/10 rounded-lg">
            <TrendingUp className="w-6 h-6 text-emerald-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">Avg. Engagement</p>
            <p className="text-2xl font-semibold text-white">0%</p>
          </div>
        </Card>
      </div>

      <Card title="Performance (Last 30 Days)">
        <div className="h-64 flex items-center justify-center border border-dashed border-slate-700 rounded-lg bg-slate-900/50">
          <div className="text-center text-slate-500 flex flex-col items-center">
            <BarChart2 className="w-8 h-8 mb-2" />
            <p>Not enough data to display chart</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Analytics;
