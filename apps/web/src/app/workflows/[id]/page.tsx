'use client';

import { use, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Zap, Loader2, Play, Pause, XCircle, Clock, CheckCircle2,
  Terminal, ShieldCheck, DollarSign, Activity, AlertTriangle
} from 'lucide-react';
import AppLayout from '../../../components/AppLayout';
import { apiFetch } from '../../../lib/api';

const STAGES = [
  'CREATED','PLANNING','RESEARCHING','ARCHITECTING','DATABASE_DESIGN',
  'BACKEND_GENERATION','FRONTEND_GENERATION','TESTING','SECURITY_REVIEW',
  'DEVOPS_GENERATION','APPROVAL_PENDING','DEPLOYING','OBSERVABILITY',
  'COST_OPTIMIZATION','AUTONOMOUS_CONTROLLER','COMPLETED',
];

const STATUS_COLORS: Record<string, string> = {
  COMPLETED: 'success', RUNNING: 'info', ACTIVE: 'info',
  PAUSED: 'warning', FAILED: 'danger', PENDING: 'warning', CREATED: 'info',
};

export default function WorkflowDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const queryClient = useQueryClient();
  const [comments, setComments] = useState('');
  const [activeTab, setActiveTab] = useState<'tasks' | 'logs' | 'approvals' | 'metrics'>('tasks');

  // Queries
  const { data: details, isLoading, error } = useQuery({
    queryKey: ['workflow-details', id],
    queryFn: () => apiFetch<any>(`/workflows/${id}`),
    refetchInterval: 5000,
  });

  const { data: logData } = useQuery({
    queryKey: ['workflow-logs', id],
    queryFn: () => apiFetch<any>(`/workflows/${id}/logs`),
    refetchInterval: 5000,
  });

  // Mutations
  const approveMutation = useMutation({
    mutationFn: () => apiFetch<any>(`/workflows/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ comments }),
    }),
    onSuccess: () => {
      setComments('');
      queryClient.invalidateQueries({ queryKey: ['workflow-details', id] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => apiFetch<any>(`/workflows/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ comments }),
    }),
    onSuccess: () => {
      setComments('');
      queryClient.invalidateQueries({ queryKey: ['workflow-details', id] });
    },
  });

  const pauseMutation = useMutation({
    mutationFn: () => apiFetch<any>(`/workflows/${id}/pause`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflow-details', id] }),
  });

  const resumeMutation = useMutation({
    mutationFn: () => apiFetch<any>(`/workflows/${id}/resume`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflow-details', id] }),
  });

  const cancelMutation = useMutation({
    mutationFn: () => apiFetch<any>(`/workflows/${id}/cancel`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflow-details', id] }),
  });

  if (isLoading) {
    return (
      <AppLayout title="Workflow details" subtitle="Loading workflow telemetry…">
        <div style={{ textAlign: 'center', padding: 80, color: 'var(--color-text-2)' }}>
          <Loader2 size={32} style={{ animation: 'spin 1s linear infinite', display: 'block', margin: '0 auto 16px' }} />
          Retrieving detailed workflow status...
        </div>
      </AppLayout>
    );
  }

  if (error || !details) {
    return (
      <AppLayout title="Workflow error" subtitle="Workflow could not be found">
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-danger)' }}>
          <XCircle size={48} style={{ display: 'block', margin: '0 auto 16px' }} />
          <h3>Error loading workflow</h3>
          <p>{error?.message || 'Workflow run does not exist'}</p>
        </div>
      </AppLayout>
    );
  }

  const stageIdx = STAGES.indexOf(details.current_state ?? '');
  const pct = stageIdx >= 0 ? Math.round((stageIdx / (STAGES.length - 1)) * 100) : 0;

  return (
    <AppLayout title={`Workflow Details`} subtitle={`Run ID: ${details.workflow_id}`}>
      {/* Header controls */}
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Workflow Pipeline Details</h1>
          <p>Project: <span className="mono">{details.project_id.slice(0, 8)}...</span> · Created: {new Date(details.created_at).toLocaleString()}</p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {details.status === 'RUNNING' && (
            <button
              onClick={() => pauseMutation.mutate()}
              disabled={pauseMutation.isPending}
              style={{
                padding: '8px 14px',
                background: 'rgba(245,158,11,0.1)',
                border: '1px solid rgba(245,158,11,0.3)',
                borderRadius: 8,
                color: 'var(--color-warning)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Pause size={14} /> Pause Run
            </button>
          )}
          {details.status === 'PAUSED' && (
            <button
              onClick={() => resumeMutation.mutate()}
              disabled={resumeMutation.isPending}
              style={{
                padding: '8px 14px',
                background: 'rgba(16,185,129,0.1)',
                border: '1px solid rgba(16,185,129,0.3)',
                borderRadius: 8,
                color: 'var(--color-success)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Play size={14} /> Resume Run
            </button>
          )}
          {(details.status === 'RUNNING' || details.status === 'PAUSED' || details.status === 'PENDING') && (
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              style={{
                padding: '8px 14px',
                background: 'rgba(239,68,68,0.1)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 8,
                color: 'var(--color-danger)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <XCircle size={14} /> Cancel
            </button>
          )}
        </div>
      </div>

      {/* Progress & Status card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className={`badge badge-${STATUS_COLORS[details.status] ?? 'info'}`} style={{ fontSize: 13, padding: '4px 10px' }}>
              {details.status}
            </span>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-2)' }}>
              Current State: <strong style={{ color: 'var(--color-text)' }}>{details.current_state?.replace(/_/g, ' ')}</strong>
            </span>
          </div>
          <span style={{ fontSize: 13, fontWeight: 600 }}>
            Completed Tasks: {details.tasks_completed} / {details.tasks_total || 15}
          </span>
        </div>

        <div style={{ height: 8, background: 'var(--color-surface-2)', borderRadius: 99, overflow: 'hidden', marginBottom: 12 }}>
          <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg, var(--color-primary), var(--color-accent))', borderRadius: 99, transition: 'width 0.8s' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--color-text-3)' }}>
          <span>{pct}% Overall pipeline progress</span>
          <span>Last updated: {new Date(details.updated_at).toLocaleTimeString()}</span>
        </div>
      </div>

      {/* HITL approval banner */}
      {details.status === 'RUNNING' && details.current_state === 'APPROVAL_PENDING' && (
        <div className="card" style={{
          border: '1px solid rgba(245,158,11,0.3)',
          background: 'rgba(245,158,11,0.06)',
          marginBottom: 24,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, fontSize: 15, fontWeight: 700, color: 'var(--color-warning)' }}>
            <AlertTriangle size={20} />
            Human Validation Barrier: Approval Required
          </div>
          <p style={{ fontSize: 13, color: 'var(--color-text-2)', marginBottom: 16 }}>
            The autonomous SDLC pipeline has successfully generated architecture layout plans and database models.
            Please review the generated artifacts and provide comments below to proceed or request adjustments.
          </p>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <textarea
              placeholder="Comments or notes (e.g. Approved. Proceed with backend code generation)"
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              rows={2}
              style={{
                flex: 1,
                padding: 10,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(245,158,11,0.25)',
                borderRadius: 8,
                color: 'var(--color-text)',
                outline: 'none',
                resize: 'none',
              }}
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending}
                style={{
                  padding: '10px 20px',
                  background: 'var(--color-success)',
                  border: 'none',
                  borderRadius: 8,
                  color: '#fff',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Approve
              </button>
              <button
                onClick={() => rejectMutation.mutate()}
                disabled={rejectMutation.isPending}
                style={{
                  padding: '8px 20px',
                  background: 'none',
                  border: '1px solid var(--color-danger)',
                  borderRadius: 8,
                  color: 'var(--color-danger)',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Reject & Re-execute
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', marginBottom: 20 }}>
        {(['tasks', 'logs', 'approvals', 'metrics'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '12px 24px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid var(--color-primary-h)' : 'none',
              color: activeTab === tab ? 'var(--color-text)' : 'var(--color-text-3)',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
              textTransform: 'capitalize',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {/* Tab 1: Tasks */}
        {activeTab === 'tasks' && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">📋 Agent SDLC Task Checklist</div>
            </div>
            {details.tasks?.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {details.tasks.map((task: any) => (
                  <div key={task.task_id} style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 14,
                    padding: 14,
                    background: 'rgba(255,255,255,0.02)',
                    borderRadius: 10,
                    border: '1px solid var(--color-border)',
                  }}>
                    <div style={{ marginTop: 2 }}>
                      {task.status === 'COMPLETED' ? (
                        <CheckCircle2 size={18} color="var(--color-success)" />
                      ) : task.status === 'RUNNING' ? (
                        <Loader2 size={18} color="var(--color-primary-h)" style={{ animation: 'spin 1s linear infinite' }} />
                      ) : (
                        <Clock size={18} color="var(--color-text-3)" />
                      )}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <strong style={{ fontSize: 13 }}>{task.title}</strong>
                        <span className={`badge badge-${STATUS_COLORS[task.status] ?? 'info'}`} style={{ fontSize: 10 }}>
                          {task.status}
                        </span>
                      </div>
                      <p style={{ fontSize: 12, color: 'var(--color-text-2)', margin: 0 }}>{task.description}</p>
                      {task.completed_at && (
                        <div style={{ fontSize: 10, color: 'var(--color-text-3)', marginTop: 8 }}>
                          Completed at: {new Date(task.completed_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-2)' }}>
                No task checklist created for this workflow run yet.
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Logs */}
        {activeTab === 'logs' && (
          <div className="card" style={{ background: '#090d16', borderColor: '#162035' }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <div className="card-title" style={{ color: '#fff', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Terminal size={16} /> Live Agent Console logs
              </div>
            </div>
            <div style={{
              fontFamily: 'monospace',
              fontSize: 12,
              color: '#38bdf8',
              background: 'rgba(0,0,0,0.3)',
              padding: 16,
              borderRadius: 8,
              minHeight: 250,
              maxHeight: 450,
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
            }}>
              {logData?.data ? (
                logData.data.map((l: any, idx: number) => (
                  <div key={idx} style={{ marginBottom: 6 }}>
                    <span style={{ color: 'var(--color-text-3)' }}>[{new Date(l.timestamp).toLocaleTimeString()}]</span>{' '}
                    <span style={{ color: '#818cf8', fontWeight: 600 }}>{l.agent_name || 'System'}:</span>{' '}
                    <span style={{ color: l.level === 'ERROR' ? 'var(--color-danger)' : '#e2e8f0' }}>{l.message}</span>
                  </div>
                ))
              ) : details.states?.length ? (
                details.states.map((s: any) => (
                  <div key={s.state_id} style={{ marginBottom: 8, color: '#94a3b8' }}>
                    <span style={{ color: '#10b981' }}>✓ Entered state: {s.state.replace(/_/g, ' ')}</span> at {new Date(s.entered_at).toLocaleTimeString()}
                    {s.exited_at && ` (Finished at ${new Date(s.exited_at).toLocaleTimeString()})`}
                  </div>
                ))
              ) : (
                <div style={{ color: 'var(--color-text-3)', textAlign: 'center', padding: '40px 0' }}>
                  No execution traces available. Starting orchestrator thread logs...
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 3: Approvals */}
        {activeTab === 'approvals' && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">⏳ Human-in-the-loop barriers history</div>
            </div>
            {details.approvals?.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Barrier Type</th>
                      <th>Status</th>
                      <th>Requested At</th>
                      <th>Decided At</th>
                      <th>Comments / Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {details.approvals.map((a: any) => (
                      <tr key={a.approval_id}>
                        <td style={{ fontWeight: 600 }}>{a.approval_type?.replace(/_/g, ' ')}</td>
                        <td>
                          <span className={`badge badge-${a.status === 'APPROVED' ? 'success' : a.status === 'REJECTED' ? 'danger' : 'warning'}`}>
                            {a.status}
                          </span>
                        </td>
                        <td className="mono" style={{ fontSize: 11 }}>{new Date(a.created_at).toLocaleString()}</td>
                        <td className="mono" style={{ fontSize: 11 }}>{a.decided_at ? new Date(a.decided_at).toLocaleString() : '—'}</td>
                        <td>{a.comments || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-2)' }}>
                No approval barriers created for this workflow run yet.
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Metrics */}
        {activeTab === 'metrics' && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">📊 LLM Token Consumption & Telemetry</div>
            </div>
            {details.metrics?.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Agent ID</th>
                      <th>Tokens Consumed</th>
                      <th>Cost (USD)</th>
                      <th>Response Time</th>
                      <th>Recorded At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {details.metrics.map((m: any) => (
                      <tr key={m.metric_id}>
                        <td>{m.agent_id}</td>
                        <td className="mono">{m.tokens_consumed?.toLocaleString() ?? 0}</td>
                        <td className="mono" style={{ color: 'var(--color-success)' }}>${m.cost_usd ? m.cost_usd.toFixed(4) : '0.0000'}</td>
                        <td className="mono">{m.latency_ms ? `${(m.latency_ms / 1000).toFixed(2)}s` : '—'}</td>
                        <td className="mono">{new Date(m.recorded_at).toLocaleTimeString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-2)' }}>
                No token metrics recorded for this workflow run yet.
              </div>
            )}
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </AppLayout>
  );
}
