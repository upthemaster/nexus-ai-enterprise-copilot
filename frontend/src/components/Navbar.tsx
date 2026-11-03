import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  BarChart3,
  Settings as SettingsIcon,
  Activity,
  ExternalLink,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../api/client';

export type ActiveTab = 'dashboard' | 'documents' | 'chat' | 'evaluation' | 'settings';

interface NavbarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onTabChange }) => {
  const [online, setOnline] = useState<boolean | null>(null);
  const [pingMs, setPingMs] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;
    const checkHeartbeat = async () => {
      const start = performance.now();
      try {
        await api.getHealth();
        if (isMounted) {
          setPingMs(Math.round(performance.now() - start));
          setOnline(true);
        }
      } catch {
        if (isMounted) {
          setOnline(false);
          setPingMs(null);
        }
      }
    };

    checkHeartbeat();
    const interval = setInterval(checkHeartbeat, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { id: 'dashboard' as ActiveTab, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'documents' as ActiveTab, label: 'Documents', icon: FileText },
    { id: 'chat' as ActiveTab, label: 'Chat & Workflows', icon: MessageSquare },
    { id: 'evaluation' as ActiveTab, label: 'Evaluation', icon: BarChart3 },
    { id: 'settings' as ActiveTab, label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-900/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-emerald-500 text-white font-bold shadow-lg shadow-indigo-500/20">
            N
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-tight text-white">NexusAI</span>
              <span className="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/20">
                COPILOT
              </span>
            </div>
            <p className="text-xs text-slate-400">Enterprise Knowledge & Workflow Platform</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1 rounded-lg bg-slate-950/60 p-1 border border-slate-800">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Status indicator & API docs */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-950 px-3 py-1 text-xs">
            {online === true ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-emerald-400 font-medium">Backend Online</span>
                {pingMs !== null && <span className="text-slate-500 font-mono text-[10px]">({pingMs}ms)</span>}
              </>
            ) : online === false ? (
              <>
                <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
                <span className="text-rose-400 font-medium">Backend Offline</span>
              </>
            ) : (
              <>
                <Activity className="h-3.5 w-3.5 text-slate-500 animate-spin" />
                <span className="text-slate-400">Checking...</span>
              </>
            )}
          </div>

          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400 hover:text-indigo-400 transition-colors"
            title="FastAPI Swagger Documentation"
          >
            <span>Swagger</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      {/* Mobile nav bar */}
      <div className="md:hidden flex border-t border-slate-800 bg-slate-950/80 px-2 py-1 justify-around">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`flex flex-col items-center gap-1 py-1 px-2 rounded text-[10px] font-medium ${
                isActive ? 'text-indigo-400' : 'text-slate-400'
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </div>
    </header>
  );
};

