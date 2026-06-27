'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Zap, Loader2, RefreshCw, Plus } from 'lucide-react';
import AppLayout from '../../components/AppLayout';
import { workflows, projects, type Workflow } from '../../lib/api';

const STATUS_COLORS: Record<string, string> = {
  COMPLETED: 'success', RUNNING: 'info', ACTIVE: 'info',
  PAUSED: 'warning', FAILED: 'danger', PENDING: 'warning', CREATED: 'info',
};

const STAGES = [
  'CREATED','PLANNING','RESEARCHING','ARCHITECTING','DATABASE_DESIGN',
  'BACKEND_GENERATION','FRONTEND_GENERATION','TESTING','SECURITY_REVIEW',
  'DEVOPS_GENERATION','APPROVAL_PENDING','DEPLOYING','OBSERVABILITY',
  'COST_OPTIMIZATION','AUTONOMOUS_CONTROLLER','COMPLETED',
];

function WorkflowCard({ wf }: { wf: Workflow }) {
  const stageIdx = STAGES.indexOf(wf.current_state ?? '');
  const pct = stageIdx >= 0 ? Math.round((stageIdx / (STAGES.length - 1)) * 100) : 0;

  return (
    <div className="card" style={{ marginBottom: 12, cursor: 'pointer' }}
      onClick={() => window.location.href = `/workflows/${wf.workflow_id}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>
            Workflow <span className="mono">{wf.workflow_id.slice(0, 8)}…</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-2)' }}>
            Stage: {wf.current_state?.replace(/_/g, ' ') ?? 'Unknown'}
          </div>
        </div>
        <span className={`badge badge-${STATUS_COLORS[wf.status] ?? 'info'}`}>{wf.status}</span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 4, background: 'var(--color-surface-2)', borderRadius: 99, overflow: 'hidden', marginBottom: 8 }}>
        <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg, var(--color-primary), var(--color-accent))', borderRadius: 99, transition: 'width 0.6s' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--color-text-3)' }}>
        <span>{pct}% complete</span>
        <span>{new Date(wf.created_at).toLocaleString()}</span>
      </div>
    </div>
  );
}

export default function WorkflowsPage() {
  const [selectedProject, setSelectedProject] = useState<string>('');

  const { data: projectList } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projects.list(0, 100),
  });

  const { data: list, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['workflows', selectedProject],
    queryFn: () => workflows.list(selectedProject || undefined, 0, 50),
    refetchInterval: 15_000,
  });

  return (
    <AppLayout title="Workflows" subtitle="All pipeline executions">
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Workflows</h1>
          <p>{list?.length ?? 0} workflows · 14-stage autonomous SDLC pipeline</p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select
            value={selectedProject}
            onChange={e => setSelectedProject(e.target.value)}
            style={{ padding: '7px 12px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text)', fontSize: 13, outline: 'none', cursor: 'pointer' }}
          >
            <option value="">All Projects</option>
            {projectList?.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
          </select>
          <button className="icon-btn" onClick={() => refetch()} title="Refresh" style={{ width: 36, height: 36 }}>
            <RefreshCw size={14} style={{ animation: isFetching ? 'spin 1s linear infinite' : 'none' }} />
          </button>
        </div>
      </div>

      {/* Stage reference */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <div className="card-title">📍 Pipeline Stage Reference</div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {STAGES.map((s, i) => (
            <span key={s} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 99, background: 'rgba(99,102,241,0.08)', color: 'var(--color-text-2)', border: '1px solid var(--color-border)' }}>
              {i + 1}. {s.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-2)' }}>
          <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', display: 'block', margin: '0 auto 12px' }} />
          Loading workflows…
        </div>
      ) : list?.length ? (
        list.map(w => <WorkflowCard key={w.workflow_id} wf={w} />)
      ) : (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <Zap size={48} style={{ opacity: 0.15, display: 'block', margin: '0 auto 16px', color: 'var(--color-primary)' }} />
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: 'var(--color-text)' }}>No workflows yet</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-2)', marginBottom: 24 }}>
            Create a project and start a workflow to see pipelines here.
          </div>
          <a href="/projects" className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: 7, textDecoration: 'none' }}>
            <Plus size={14} /> Go to Projects
          </a>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </AppLayout>
  );
}
