'use client';

import { useQuery } from '@tanstack/react-query';
import {
  GitBranch, CheckCircle, DollarSign, Zap,
  TrendingUp, AlertTriangle, Clock,
} from 'lucide-react';
import AppLayout from '../components/AppLayout';
import { enterprise, projects, workflows, approvals, observability } from '../lib/api';

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({
  icon: Icon, iconClass, value, label, delta, up, loading,
}: {
  icon: React.ElementType; iconClass: string; value: string | number;
  label: string; delta?: string; up?: boolean; loading?: boolean;
}) {
  return (
    <div className="stat-card fade-in">
      <div className={`stat-icon ${iconClass}`}><Icon /></div>
      <div className="stat-value">{loading ? '—' : value}</div>
      <div className="stat-label">{label}</div>
      {delta && (
        <div className={`stat-delta ${up ? 'up' : 'down'}`}>
          <TrendingUp size={10} />{delta}
        </div>
      )}
    </div>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['enterprise-stats'],
    queryFn: () => enterprise.stats(),
    refetchInterval: 15_000,
  });

  const { data: projectList, isLoading: projLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projects.list(0, 10),
    refetchInterval: 30_000,
  });

  const { data: workflowList, isLoading: wfLoading } = useQuery({
    queryKey: ['workflows'],
    queryFn: () => workflows.list(undefined, 0, 10),
    refetchInterval: 15_000,
  });

  const { data: pendingApprovals } = useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: () => approvals.list('pending'),
    refetchInterval: 10_000,
  });

  const { data: agentList } = useQuery({
    queryKey: ['agents'],
    queryFn: () => observability.agents(),
    refetchInterval: 10_000,
  });

  const statusColor: Record<string, string> = {
    COMPLETED: 'success', RUNNING: 'info', ACTIVE: 'info',
    PAUSED: 'warning', FAILED: 'danger', PENDING: 'warning',
  };

  const agentStatusDotClass: Record<string, string> = {
    healthy: 'healthy', busy: 'busy', idle: 'idle',
    active: 'busy', offline: 'idle',
  };

  return (
    <AppLayout title="Dashboard" subtitle="Real-time SDLC Overview">
      {/* Section header */}
      <div className="section-header">
        <h1>Autonomous SDLC Control Center</h1>
        <p>
          {statsLoading ? 'Loading...' : `${stats?.total_projects ?? 0} projects · ${stats?.total_workflows ?? 0} workflows · ${stats?.pending_approvals ?? 0} pending approvals`}
        </p>
      </div>

      {/* Stats */}
      <div className="stat-grid">
        <StatCard icon={GitBranch}   iconClass="indigo" value={stats?.total_projects ?? '—'}        label="Total Projects"          loading={statsLoading} />
        <StatCard icon={CheckCircle} iconClass="green"  value={stats?.workflows_completed ?? '—'}   label="Workflows Completed"     loading={statsLoading} />
        <StatCard icon={Zap}         iconClass="cyan"   value={stats?.workflows_active ?? '—'}      label="Active Workflows"        loading={statsLoading} />
        <StatCard icon={Clock}       iconClass="amber"  value={stats?.pending_approvals ?? '—'}     label="Pending Approvals"       loading={statsLoading} />
      </div>

      {/* Row: Workflows + Agents */}
      <div className="grid-row cols-7-5" style={{ marginBottom: 20 }}>

        {/* Recent Workflows */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">⚡ Recent Workflows</div>
              <div className="card-subtitle">Latest pipeline executions</div>
            </div>
            <a href="/workflows" className="card-action">View all</a>
          </div>
          {wfLoading ? (
            <p style={{ color: 'var(--color-text-2)', fontSize: 13 }}>Loading workflows…</p>
          ) : workflowList?.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Project</th>
                    <th>Stage</th>
                    <th>Status</th>
                    <th>Progress</th>
                  </tr>
                </thead>
                <tbody>
                  {workflowList.map(w => (
                    <tr key={w.workflow_id} style={{ cursor: 'pointer' }} onClick={() => window.location.href = `/workflows/${w.workflow_id}`}>
                      <td className="mono">{w.workflow_id.slice(0, 8)}…</td>
                      <td style={{ fontSize: 12, color: 'var(--color-text-2)' }}>{w.current_state?.replace(/_/g, ' ')}</td>
                      <td>
                        <span className={`badge badge-${statusColor[w.status] ?? 'info'}`}>{w.status}</span>
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {w.tasks_total > 0 ? `${w.tasks_completed}/${w.tasks_total}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--color-text-2)', fontSize: 13 }}>
              <Zap size={32} style={{ opacity: 0.2, display: 'block', margin: '0 auto 12px' }} />
              No workflows yet. Create a project and start a workflow.
            </div>
          )}
        </div>

        {/* Agent Health */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">🤖 Agent Health</div>
              <div className="card-subtitle">{agentList?.length ?? 0} agents monitored</div>
            </div>
            <a href="/agents" className="card-action">Monitor</a>
          </div>
          {agentList?.length ? (
            <div className="agent-grid">
              {agentList.map(a => (
                <div key={a.agent_id} className="agent-card">
                  <div className={`agent-status-dot ${agentStatusDotClass[a.status] ?? 'idle'}`} />
                  <div className="agent-name">{a.agent_type?.replace(/_/g, ' ')}</div>
                  <div className="agent-tasks">{a.tasks_completed} done</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-2)', fontSize: 13 }}>
              No agent data yet
            </div>
          )}
        </div>
      </div>

      {/* Row: Projects + Approvals */}
      <div className="grid-row cols-2">

        {/* Projects */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">📋 Projects</div>
              <div className="card-subtitle">{projectList?.length ?? 0} total</div>
            </div>
            <a href="/projects" className="card-action">Manage</a>
          </div>
          {projLoading ? (
            <p style={{ color: 'var(--color-text-2)', fontSize: 13 }}>Loading…</p>
          ) : projectList?.length ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Name</th><th>Budget</th><th>Created</th></tr></thead>
                <tbody>
                  {projectList.map(p => (
                    <tr key={p.project_id}>
                      <td style={{ fontWeight: 600 }}>{p.name}</td>
                      <td className="mono">${Number(p.budget_usd_limit).toFixed(2)}</td>
                      <td className="mono">{new Date(p.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--color-text-2)', fontSize: 13 }}>
              <GitBranch size={32} style={{ opacity: 0.2, display: 'block', margin: '0 auto 12px' }} />
              No projects yet.{' '}
              <a href="/projects" style={{ color: 'var(--color-primary-h)' }}>Create your first project →</a>
            </div>
          )}
        </div>

        {/* Pending Approvals */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">⏳ Pending Approvals</div>
              <div className="card-subtitle">{pendingApprovals?.length ?? 0} awaiting review</div>
            </div>
            {(pendingApprovals?.length ?? 0) > 0 && (
              <span className="badge badge-warning">{pendingApprovals!.length} pending</span>
            )}
          </div>
          {pendingApprovals?.length ? (
            pendingApprovals.map(a => (
              <div key={a.approval_id} className="approval-item">
                <div className="approval-icon"><AlertTriangle /></div>
                <div className="approval-info">
                  <div className="approval-title">{a.approval_type?.replace(/_/g, ' ')}</div>
                  <div className="approval-sub">
                    Workflow {a.workflow_id.slice(0, 8)}… · {new Date(a.requested_at).toLocaleTimeString()}
                  </div>
                </div>
                <a href="/approvals" className="btn-approve">Review</a>
              </div>
            ))
          ) : (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--color-text-2)', fontSize: 13 }}>
              <CheckCircle size={32} style={{ opacity: 0.2, display: 'block', margin: '0 auto 12px' }} />
              No pending approvals
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
