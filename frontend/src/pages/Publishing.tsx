import React from 'react';
import Card from '../components/Card';
import EmptyState from '../components/EmptyState';
import { Send } from 'lucide-react';

const Publishing = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Publishing</h1>
      
      <Card>
        <EmptyState 
          icon={Send}
          title="No videos ready to publish"
          description="Generate a video first, then you can publish it directly to your connected channels from here."
        />
      </Card>
    </div>
  );
};

export default Publishing;
