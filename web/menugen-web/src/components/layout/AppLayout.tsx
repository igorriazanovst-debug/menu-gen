import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { SyncIndicator } from './SyncIndicator'; // MG_T08

export const AppLayout: React.FC = () => (
  <div className="flex min-h-screen bg-bg">
    <Sidebar />
    <main className="flex-1 p-6 overflow-auto">
      {/* MG_SKIN: wider canvas for the dashboard grid; inner pages stay readable. */}
      <div className="max-w-7xl mx-auto">
        {/* MG_T08: global sync status indicator */}
        <div className="flex justify-end mb-2">
          <SyncIndicator />
        </div>
        <Outlet />
      </div>
    </main>
  </div>
);
