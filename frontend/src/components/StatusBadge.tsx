import React from 'react';

type StatusType = 'queued' | 'processing' | 'completed' | 'failed' | 'draft' | 'published';

interface StatusBadgeProps {
  status: string;
}

const getStatusConfig = (status: string) => {
  const s = status.toLowerCase();
  if (['completed', 'published', 'active'].includes(s)) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  if (['failed', 'error'].includes(s)) return 'bg-red-500/10 text-red-400 border-red-500/20';
  if (['processing', 'generating', 'rendering'].includes(s)) return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
  return 'bg-amber-500/10 text-amber-400 border-amber-500/20'; // queued, draft, pending
};

const StatusBadge = ({ status }: StatusBadgeProps) => {
  const config = getStatusConfig(status);
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${config}`}>
      {status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
    </span>
  );
};

export default StatusBadge;
