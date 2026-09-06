import React, { useEffect, useState } from 'react';
import Card from '../components/Card';
import StatusBadge from '../components/StatusBadge';
import EmptyState from '../components/EmptyState';
import Modal from '../components/Modal';
import { Tv, Plus } from 'lucide-react';
import { Channel } from '../types';
import { listChannels, createChannel } from '../api/channels';
import toast from 'react-hot-toast';

const Channels = () => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newChannel, setNewChannel] = useState({ name: '', description: '' });

  useEffect(() => {
    loadChannels();
  }, []);

  const loadChannels = async () => {
    setLoading(true);
    try {
      const data = await listChannels();
      setChannels(data);
    } catch (error) {
      toast.error('Failed to load channels');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createChannel(newChannel);
      toast.success('Channel created successfully');
      setIsModalOpen(false);
      setNewChannel({ name: '', description: '' });
      loadChannels();
    } catch (error) {
      toast.error('Failed to create channel');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Channels</h1>
          <p className="text-sm text-slate-400">Manage your connected social accounts and channels</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setIsModalOpen(true)}>
          <Plus className="w-4 h-4" />
          Add Channel
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading channels...</div>
      ) : channels.length === 0 ? (
        <Card>
          <EmptyState
            icon={Tv}
            title="No channels found"
            description="Connect a channel to start generating and publishing content."
            action={
              <button className="btn-primary mt-4" onClick={() => setIsModalOpen(true)}>
                Add your first channel
              </button>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {channels.map((channel) => (
            <Card key={channel.id} className="flex flex-col">
              <div className="flex justify-between items-start mb-4">
                <div className="w-12 h-12 bg-indigo-500/20 text-indigo-400 rounded-lg flex items-center justify-center">
                  <Tv className="w-6 h-6" />
                </div>
                <StatusBadge status={channel.status} />
              </div>
              <h3 className="text-lg font-semibold text-white mb-1">{channel.name}</h3>
              {channel.handle && <p className="text-sm text-slate-400 mb-4">{channel.handle}</p>}
              <p className="text-sm text-slate-300 mb-6 flex-1 line-clamp-2">{channel.description}</p>
              
              <div className="pt-4 border-t border-slate-800 flex justify-between items-center text-sm">
                <span className="text-slate-400">Autopilot: <span className={channel.autopilot_enabled ? 'text-green-400' : 'text-slate-500'}>{channel.autopilot_enabled ? 'On' : 'Off'}</span></span>
                <button className="text-primary-400 hover:text-primary-300 font-medium">Manage</button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Add New Channel">
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Channel Name</label>
            <input 
              required
              type="text" 
              className="input-field" 
              value={newChannel.name}
              onChange={(e) => setNewChannel({ ...newChannel, name: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Description</label>
            <textarea 
              className="input-field min-h-[100px]" 
              value={newChannel.description}
              onChange={(e) => setNewChannel({ ...newChannel, description: e.target.value })}
            />
          </div>
          <div className="pt-4 flex justify-end gap-3">
            <button type="button" className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
            <button type="submit" className="btn-primary">Create Channel</button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Channels;
