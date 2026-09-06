import React from 'react';
import Card from '../components/Card';
import { useAuth } from '../auth/AuthContext';

const Settings = () => {
  const { user, logout } = useAuth();

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      <Card title="Profile Information">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Name</label>
            <input type="text" className="input-field" defaultValue={user?.name} readOnly />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Email</label>
            <input type="email" className="input-field" defaultValue={user?.email} readOnly />
          </div>
        </div>
      </Card>

      <Card title="API Keys">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Pexels API Key</label>
            <input type="password" className="input-field" placeholder="••••••••••••••••" />
          </div>
          <div className="pt-2">
            <button className="btn-primary">Save Keys</button>
          </div>
        </div>
      </Card>

      <Card title="Account Actions" className="border-red-500/20">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-white font-medium">Sign Out</h4>
            <p className="text-sm text-slate-400">Log out of your current session</p>
          </div>
          <button onClick={logout} className="btn-secondary text-red-400 border-red-500/20 hover:bg-red-500/10 hover:border-red-500/30">
            Sign Out
          </button>
        </div>
      </Card>
    </div>
  );
};

export default Settings;
