import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';

export const AppLayout: React.FC = () => (
  <div className="flex min-h-screen bg-rice">
    <Sidebar />
    <main className="flex-1 p-6 overflow-auto">
      <div className="max-w-5xl mx-auto">
        <Outlet />
      </div>
    </main>
  </div>
);
