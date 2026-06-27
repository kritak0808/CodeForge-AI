'use client';

import { useQuery } from '@tanstack/react-query';
import { Cpu, Loader2 } from 'lucide-react';
import AppLayout from '../../components/AppLayout';
import { observability, type AgentHealth } from '../../lib/api';

const STATUS_CONFIG: Record<string, { cls: string; label: string }> = {
  healthy: { cls: 'healthy', label: 'Healthy' },
  busy:    { cls: 'busy',    label: 'Busy' },
  active:  { cls: 'busy',   label: 'Active' },
  idle:    { cls: 'idle',   label: 'Idle' },
  offline: { cls: 'idle',   label: 'Offline' },
};

function AgentRow({ agent }: { agent: AgentHealth }) {
  const sc = STATUS_CONFIG[agent.status] ?? STATUS_CONFIG.idle;
  const successRate = agent.tasks_completed + agent.tasks_failed > 0
    ? Math.round((agent.tasks_completed / (agent.tasks_completed + agent.tasks_failed)) * 100)
    : 100;

  return (
    <tr>
      <td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className={`agent-status-dot ${sc.cls}`} />
          <div style={{ fontWeight: 600 }}>{agent.agent_type?.replace(/_/g, ' ')}</div>
        </div>
      </td>
      <td><span className={`badge badge-${sc.cls === 'healthy' ? 'success' : sc.cls === 'busy' ? 'info' : 'warning'}`}>{sc.label}</span></td>
      <td className="mono">{agent.tasks_completed}</td>
      <td className="mono">{agent.tasks_failed}</td>
      <td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ flex: 1, height: 5, background: 'var(--color-surface-2)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${successRate}%`, background: successRate > 90 ? 'var(--color-success)' : successRate > 70 ? 'var(--color-warning)' : 'var(--color-danger)', borderRadius: 99 }} />
          </div>
          <span style={{ fontSize: 11, color: 'var(--color-text-2)', minWidth: 28 }}>{successRate}%</span>
        </div>
      </td>
      <td className="mono">{agent.avg_duration_ms > 0 ? `${(agent.avg_duration_ms / 1000).toFixed(1)}s` : '—'}</td>
      <td className="mono">{new Date(agent.last_heartbeat).toLocaleTimeString()}</td>
    </tr>
  );
}

export default function AgentsPage() {
  const { data: agents, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['agents'],
    queryFn: () => observability.agents(),
    refetchInterval: 8_000,
  });

  const healthy = agents?.filter(a => a.status === 'healthy').length ?? 0;
  const busy    = agents?.filter(a => ['busy','active'].includes(a.status)).length ?? 0;
  const offline = agents?.filter(a => a.status === 'offline').length ?? 0;

  return (
    <AppLayout title="Agents" subtitle="Real-time agent health monitor">
      <div className="section-header">
        <h1>Agent Health Monitor</h1>
        <p>
          {agents?.length ?? 0} agents total ·{' '}
          <span style={{ color: 'var(--color-success)' }}>{healthy} healthy</span> ·{' '}
          <span style={{ color: 'var(--color-warning)' }}>{busy} busy</span> ·{' '}
          <span style={{ color: 'var(--color-text-3)' }}>{offline} offline</span>
          {dataUpdatedAt > 0 && <span style={{ marginLeft: 12, color: 'var(--color-text-3)', fontSize: 11 }}>
            Updated {new Date(dataUpdatedAt).toLocaleTimeString()}
          </span>}
        </p>
      </div>

      {/* Summary Cards */}
      <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 24 }}>
        {[
          { label: 'Healthy', value: healthy, color: 'var(--color-success)' },
          { label: 'Busy / Active', value: busy, color: 'var(--color-warning)' },
          { label: 'Offline', value: offline, color: 'var(--color-text-3)' },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">🤖 All Agents</div>
          <div className="card-subtitle">Auto-refreshes every 8 seconds</div>
        </div>

        {isLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-2)' }}>
            <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', display: 'block', margin: '0 auto 12px' }} />
            Loading agents…
          </div>
        ) : agents?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Status</th>
                  <th>Completed</th>
                  <th>Failed</th>
                  <th>Success Rate</th>
                  <th>Avg Duration</th>
                  <th>Last Heartbeat</th>
                </tr>
              </thead>
              <tbody>
                {agents.map(a => <AgentRow key={a.agent_id} agent={a} />)}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--color-text-2)' }}>
            <Cpu size={40} style={{ opacity: 0.15, display: 'block', margin: '0 auto 14px' }} />
            <div style={{ fontWeight: 600, marginBottom: 6 }}>No agent data available</div>
            <div style={{ fontSize: 13 }}>Agents register when workflows start executing.</div>
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </AppLayout>
  );
}
