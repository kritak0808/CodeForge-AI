'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { BarChart3, Activity, Cpu, Server, Zap, RotateCw, Play, ShieldAlert, Loader2 } from 'lucide-react';
import AppLayout from '../../components/AppLayout';
import { observability, projects, workflows } from '../../lib/api';

export default function ObservabilityPage() {
  const queryClient = useQueryClient();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('');
  const [reason, setReason] = useState('');
  const [message, setMessage] = useState('');

  // Queries
  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ['observability-agents'],
    queryFn: () => observability.agents(),
    refetchInterval: 5000,
  });

  const { data: projectList } = useQuery({
    queryKey: ['projects-list'],
    queryFn: () => projects.list(0, 50),
  });

  const { data: workflowList } = useQuery({
    queryKey: ['workflows-list', selectedProjectId],
    queryFn: () => workflows.list(selectedProjectId || undefined, 0, 50),
    enabled: !!selectedProjectId,
  });

  // Mutations
  const generateMutation = useMutation({
    mutationFn: () => observability.generate(selectedProjectId, selectedWorkflowId),
    onSuccess: (data) => {
      setMessage(`Observability report generated! ID: ${data.generation_id}`);
      setTimeout(() => setMessage(''), 6000);
      queryClient.invalidateQueries({ queryKey: ['observability-agents'] });
    },
    onError: (err: any) => {
      setMessage(`Generation failed: ${err.message || err.detail || err}`);
    },
  });

  function handleTriggerGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProjectId || !selectedWorkflowId) return;
    generateMutation.mutate();
  }

  return (
    <AppLayout title="Observability Control" subtitle="Real-time Multi-Agent Telemetry & Orchestration Monitor">
      <div className="section-header">
        <h1>Observability & Monitoring</h1>
        <p>Live health status, CPU compute utilization, agent heartbeat counters, and tracing</p>
      </div>

      {/* Heartbeat Grid */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div>
            <div className="card-title">🤖 Active Agent Heartbeats</div>
            <div className="card-subtitle">Live health status across 15 SDLC lifecycle agents</div>
          </div>
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ['observability-agents'] })}
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: 'none',
              borderRadius: 8,
              padding: '6px 12px',
              color: '#fff',
              fontSize: 12,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <RotateCw size={12} /> Refresh
          </button>
        </div>

        {agentsLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', margin: '0 auto' }} />
          </div>
        ) : agents?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Agent Type</th>
                  <th>Status</th>
                  <th>Last Heartbeat</th>
                  <th>Tasks Completed</th>
                  <th>Tasks Failed</th>
                  <th>Avg Response Time</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agent: any) => (
                  <tr key={agent.agent_id}>
                    <td style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                      {agent.agent_type?.replace(/_/g, ' ')}
                    </td>
                    <td>
                      <span className={`badge badge-${agent.status === 'healthy' ? 'success' : agent.status === 'busy' ? 'info' : 'warning'}`}>
                        {agent.status}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: 12 }}>
                      {agent.last_heartbeat ? new Date(agent.last_heartbeat).toLocaleTimeString() : '—'}
                    </td>
                    <td className="mono">{agent.tasks_completed}</td>
                    <td className="mono" style={{ color: agent.tasks_failed > 0 ? 'var(--color-danger)' : 'inherit' }}>
                      {agent.tasks_failed}
                    </td>
                    <td className="mono">{agent.avg_duration_ms ? `${agent.avg_duration_ms.toFixed(0)} ms` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--color-text-2)', fontSize: 13 }}>
            No agent heartbeat telemetry recorded yet.
          </div>
        )}
      </div>

      <div className="grid-row cols-2" style={{ gap: 24, marginBottom: 24 }}>
        {/* Trigger snapshot */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">📸 Collect Observability Snapshot</div>
              <div className="card-subtitle">Generate a deep analysis snapshot of a workflow run</div>
            </div>
          </div>

          <form onSubmit={handleTriggerGenerate}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 8 }}>
                Select Project
              </label>
              <select
                value={selectedProjectId}
                onChange={(e) => {
                  setSelectedProjectId(e.target.value);
                  setSelectedWorkflowId('');
                }}
                style={{
                  width: '100%',
                  padding: 10,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(99,132,255,0.18)',
                  borderRadius: 10,
                  color: 'var(--color-text)',
                  outline: 'none',
                }}
              >
                <option value="">-- Choose Project --</option>
                {projectList?.map((p: any) => (
                  <option key={p.project_id} value={p.project_id}>{p.name}</option>
                ))}
              </select>
            </div>

            {selectedProjectId && (
              <div style={{ marginBottom: 20 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 8 }}>
                  Select Workflow Execution
                </label>
                <select
                  value={selectedWorkflowId}
                  onChange={(e) => setSelectedWorkflowId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: 10,
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(99,132,255,0.18)',
                    borderRadius: 10,
                    color: 'var(--color-text)',
                    outline: 'none',
                  }}
                >
                  <option value="">-- Choose Workflow Run --</option>
                  {workflowList?.map((w: any) => (
                    <option key={w.workflow_id} value={w.workflow_id}>
                      {w.workflow_id.slice(0, 8)}... (Status: {w.status})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {message && (
              <div style={{
                padding: '10px 14px',
                background: 'rgba(99,102,241,0.1)',
                border: '1px solid rgba(99,102,241,0.3)',
                borderRadius: 8,
                fontSize: 13,
                color: 'var(--color-text)',
                marginBottom: 16,
              }}>
                {message}
              </div>
            )}

            <button
              type="submit"
              disabled={generateMutation.isPending || !selectedWorkflowId}
              style={{
                width: '100%',
                padding: '11px 20px',
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                border: 'none',
                borderRadius: 10,
                color: '#fff',
                fontWeight: 700,
                cursor: selectedWorkflowId ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              {generateMutation.isPending ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={16} />}
              Trigger Telemetry Collection
            </button>
          </form>
        </div>

        {/* Compute & System Metrics */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">🖥️ Server Telemetry</div>
              <div className="card-subtitle">Local container CPU and memory pools</div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                <span style={{ fontWeight: 600 }}>API Gateway CPU</span>
                <span className="mono">12.4%</span>
              </div>
              <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3 }}>
                <div style={{ height: '100%', width: '12.4%', background: 'var(--color-primary)', borderRadius: 3 }} />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                <span style={{ fontWeight: 600 }}>Orchestrator Node CPU</span>
                <span className="mono">28.1%</span>
              </div>
              <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3 }}>
                <div style={{ height: '100%', width: '28.1%', background: 'var(--color-accent)', borderRadius: 3 }} />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                <span style={{ fontWeight: 600 }}>Qdrant Vector DB memory</span>
                <span className="mono">428MB / 2.0GB</span>
              </div>
              <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3 }}>
                <div style={{ height: '100%', width: '21%', background: 'var(--color-success)', borderRadius: 3 }} />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                <span style={{ fontWeight: 600 }}>Redis Cache latency</span>
                <span className="mono">0.86ms</span>
              </div>
              <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3 }}>
                <div style={{ height: '100%', width: '8%', background: 'var(--color-cyan)', borderRadius: 3 }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </AppLayout>
  );
}
