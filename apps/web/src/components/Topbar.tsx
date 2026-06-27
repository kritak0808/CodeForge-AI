'use client';

import { Bell, RefreshCw, Search } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { health } from '../lib/api';

interface TopbarProps {
  title: string;
  subtitle?: string;
}

export default function Topbar({ title, subtitle }: TopbarProps) {
  const { data: status } = useQuery({
    queryKey: ['health'],
    queryFn: () => health.check(),
    refetchInterval: 30_000,
    retry: false,
  });

  const online = status?.status === 'ok' || status?.status === 'healthy';

  return (
    <header className="topbar">
      <div className="topbar-title">
        {title}
        {subtitle && (
          <span className="topbar-subtitle" style={{ marginLeft: 10, fontWeight: 400 }}>
            — {subtitle}
          </span>
        )}
      </div>
      <div className="topbar-actions">
        <div
          className="status-dot"
          style={{ background: online ? 'var(--color-success)' : 'var(--color-danger)' }}
          title={online ? 'API connected' : 'API offline'}
        />
        <span style={{ fontSize: 12, color: 'var(--color-text-2)' }}>
          {online ? 'API connected' : 'API offline'}
        </span>
        <button className="icon-btn" title="Search">
          <Search size={15} />
        </button>
        <button className="icon-btn" title="Notifications">
          <Bell size={15} />
        </button>
        <button className="icon-btn" title="Refresh" onClick={() => window.location.reload()}>
          <RefreshCw size={15} />
        </button>
      </div>
    </header>
  );
}
