'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Database, Settings, Activity, ShieldCheck, Flag, Plus, Loader2, Sparkles } from 'lucide-react';
import AppLayout from '../../components/AppLayout';
import { enterprise, health } from '../../lib/api';

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [flagName, setFlagName] = useState('');
  const [flagEnabled, setFlagEnabled] = useState(true);
  const [flagRules, setFlagRules] = useState('{"roles": ["admin"]}');
  const [flagMessage, setFlagMessage] = useState('');

  // Queries
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['enterprise-stats'],
    queryFn: () => enterprise.stats(),
    refetchInterval: 10_000,
  });

  const { data: healthStatus, isLoading: healthLoading } = useQuery({
    queryKey: ['health-check'],
    queryFn: () => health.check(),
    refetchInterval: 15_000,
  });

  // Mutations
  const createFlagMutation = useMutation({
    mutationFn: (data: { name: string; is_enabled: boolean; rules_json: any }) =>
      enterprise.createFlag(data),
    onSuccess: () => {
      setFlagName('');
      setFlagMessage('Feature flag registered successfully!');
      setTimeout(() => setFlagMessage(''), 5000);
      queryClient.invalidateQueries({ queryKey: ['feature-flags'] });
    },
    onError: (err: any) => {
      setFlagMessage(`Failed to create flag: ${err.message || err.detail || err}`);
    },
  });

  function handleCreateFlag(e: React.FormEvent) {
    e.preventDefault();
    if (!flagName.trim()) return;
    let rules = {};
    try {
      if (flagRules.trim()) {
        rules = JSON.parse(flagRules);
      }
    } catch {
      setFlagMessage('Invalid JSON rules format');
      return;
    }
    createFlagMutation.mutate({
      name: flagName.trim(),
      is_enabled: flagEnabled,
      rules_json: rules,
    });
  }

  return (
    <AppLayout title="Admin Portal" subtitle="System Diagnostics & Feature Configuration Control">
      <div className="section-header">
        <h1>Administrative Platform Portal</h1>
        <p>Manage global platform settings, inspect microservices connection status, and roll out feature flags</p>
      </div>

      {/* Row 1: Health Diagnostics + Feature Flags */}
      <div className="grid-row cols-2" style={{ gap: 24, marginBottom: 24 }}>
        {/* Connection Diagnostics */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">🔌 Connection Diagnostics</div>
              <div className="card-subtitle">Microservices status and database pings</div>
            </div>
          </div>

          {healthLoading ? (
            <div style={{ textAlign: 'center', padding: 30 }}>
              <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto' }} />
            </div>
          ) : healthStatus ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>API Gateway Server</span>
                <span className="badge badge-success">{healthStatus.status}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>SQL Relational Database</span>
                <span className={`badge badge-${healthStatus.database === 'connected' ? 'success' : 'danger'}`}>
                  {healthStatus.database}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Redis Cache cluster</span>
                <span className={`badge badge-${healthStatus.redis?.includes('connected') || healthStatus.redis === 'mocked' || healthStatus.redis === 'connected' ? 'success' : 'warning'}`}>
                  {healthStatus.redis}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Apache Kafka Broker</span>
                <span className={`badge badge-${healthStatus.kafka === 'connected' || healthStatus.kafka === 'disabled' ? 'success' : 'warning'}`}>
                  {healthStatus.kafka}
                </span>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>Failed to retrieve connection health check details.</div>
          )}
        </div>

        {/* Feature Flag Management */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">🚩 Feature Flag Deployment</div>
              <div className="card-subtitle">Roll out and toggle features dynamically</div>
            </div>
          </div>

          <form onSubmit={handleCreateFlag}>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>
                Flag Name
              </label>
              <input
                type="text"
                placeholder="e.g. use-gemini-3.5-flash"
                value={flagName}
                onChange={(e) => setFlagName(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: 10,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(99,132,255,0.18)',
                  borderRadius: 8,
                  color: 'var(--color-text)',
                  outline: 'none',
                }}
              />
            </div>

            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
              <input
                type="checkbox"
                id="flagEnabled"
                checked={flagEnabled}
                onChange={(e) => setFlagEnabled(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <label htmlFor="flagEnabled" style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)', cursor: 'pointer' }}>
                Enable Flag by Default
              </label>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>
                Targeting Rules (JSON)
              </label>
              <textarea
                rows={2}
                value={flagRules}
                onChange={(e) => setFlagRules(e.target.value)}
                style={{
                  width: '100%',
                  padding: 10,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(99,132,255,0.18)',
                  borderRadius: 8,
                  color: 'var(--color-text)',
                  fontFamily: 'monospace',
                  fontSize: 12,
                  outline: 'none',
                  resize: 'none',
                }}
              />
            </div>

            {flagMessage && (
              <div style={{
                padding: '8px 12px',
                background: 'rgba(99,102,241,0.1)',
                border: '1px solid rgba(99,102,241,0.3)',
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--color-text)',
                marginBottom: 12,
              }}>
                {flagMessage}
              </div>
            )}

            <button
              type="submit"
              disabled={createFlagMutation.isPending || !flagName.trim()}
              style={{
                width: '100%',
                padding: 10,
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                border: 'none',
                borderRadius: 8,
                color: '#fff',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
              }}
            >
              {createFlagMutation.isPending ? <Loader2 size={16} style={{ animation: 'spin 1s linear' }} /> : <Plus size={16} />}
              Create Feature Flag
            </button>
          </form>
        </div>
      </div>

      {/* Aggregate Stats Cards */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">📊 Platform Aggregate Counters</div>
            <div className="card-subtitle">Real-time usage totals and users registration</div>
          </div>
        </div>

        {statsLoading ? (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto' }} />
          </div>
        ) : stats ? (
          <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
            <div className="stat-card">
              <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-primary-h)' }}>{stats.total_projects}</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-2)', marginTop: 4 }}>Projects</div>
            </div>
            <div className="stat-card">
              <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-success)' }}>{stats.workflows_completed}</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-2)', marginTop: 4 }}>Completed Workflows</div>
            </div>
            <div className="stat-card">
              <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-cyan)' }}>{stats.workflows_active}</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-2)', marginTop: 4 }}>Active Workflows</div>
            </div>
            <div className="stat-card">
              <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-text)' }}>{stats.total_users}</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-2)', marginTop: 4 }}>Registered Users</div>
            </div>
            <div className="stat-card">
              <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-warning)' }}>{stats.pending_approvals}</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-2)', marginTop: 4 }}>Awaiting Approvals</div>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--color-text-2)' }}>No statistics counters returned.</div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </AppLayout>
  );
}
