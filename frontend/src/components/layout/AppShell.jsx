import React, { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import ToastContainer from '@components/feedback/ToastContainer'
import SW from '@constants/sw'

// Same build artifact is deployed to both pos.cctvpoint.org and
// demo.cctvpoint.org (see frontend/.env.production — VITE_API_BASE_URL is
// intentionally empty so API calls are same-origin relative paths). This
// check is purely a runtime visual cue so nobody mistakes the demo for
// production; it has no effect on which backend/database is actually used.
const isDemo = typeof window !== 'undefined' && window.location.hostname.startsWith('demo.')

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="flex h-screen bg-bg overflow-hidden">
      <Sidebar open={sidebarOpen} onToggle={() => setSidebarOpen((v) => !v)} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {isDemo && (
          <div className="bg-accent-yellow text-black text-xs font-semibold text-center py-1 flex-shrink-0">
            {SW.demoRibbon}
          </div>
        )}
        <TopBar onMenuClick={() => setSidebarOpen((v) => !v)} />
        <main className="flex-1 overflow-y-auto">
          <div className="p-6 min-h-full">
            <Outlet />
          </div>
        </main>
      </div>
      <ToastContainer />
    </div>
  )
}
