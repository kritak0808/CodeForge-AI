'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle, XCircle, Clock, Loader2, AlertTriangle } from 'lucide-react';
import AppLayout from '../../components/AppLayout';
import { approvals, type Approval } from '../../lib/api';
import { useState } from 'react';

const STATUS_COLORS: Record<string, string> = {
  pending: 'warning', approved: 'success', rejected: 'danger', expired: 'info',
};

function ApprovalCard({ approval }: { approval: Approval }) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState('');

  const approveMut = useMutation({
    mutationFn: () => approvals.approve(approval.approval_id, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['approvals'] }),
  });

  const rejectMut = useMutation({
    mutationFn: () => approvals.reject(approval.approval_id, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['approvals'] }),
  });

  const isPending = approval.status === 'pending';
  const loading = approveMut.isPending || rejectMut.isPending;

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 10, flexShrink: 0,
          background: isPending ? 'rgba(245,158,11,0.1)' : approval.status === 'approved' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: isPending ? 'var(--color-warning)' : approval.status === 'approved' ? 'var(--color-success)' : 'var(--color-danger)',
        }}>
          {isPending ? <AlertTriangle size={20} /> : approval.status === 'approved' ? <CheckCircle size={20} /> : <XCircle size={20} />}
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <div style={{ fontWeight: 700, fontSize: 14 }}>
              {approval.approval_type?.replace(/_/g, ' ')}
            </div>
            <span className={`badge badge-${STATUS_COLORS[approval.status] ?? 'info'}`}>
              {approval.status}
            </span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-2)', marginBottom: 4 }}>
            Workflow: <span className="mono">{approval.workflow_id.slice(0, 12)}…</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-3)', display: 'flex', gap: 16 }}>
            <span><Clock size={10} style={{ verticalAlign: 'middle' }} /> Requested: {new Date(approval.requested_at).toLocaleString()}</span>
            {approval.decided_at && <span>Decided: {new Date(approval.decided_at).toLocaleString()}</span>}
          </div>
          {approval.notes && (
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-2)', background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: '6px 10px' }}>
              Notes: {approval.notes}
            </div>
          )}
        </div>
      </div>

      {isPending && (
        <div style={{ marginTop: 16, borderTop: '1px solid var(--color-border)', paddingTop: 16 }}>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Optional notes…"
            rows={2}
            style={{ width: '100%', padding: '8px 12px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text)', fontSize: 13, outline: 'none', resize: 'none', marginBottom: 12, boxSizing: 'border-box', fontFamily: 'var(--font-sans)' }}
          />
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              id={`reject-${approval.approval_id}`}
              className="btn"
              disabled={loading}
              onClick={() => rejectMut.mutate()}
              style={{ flex: 1, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--color-danger)' }}
            >
              {rejectMut.isPending ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <XCircle size={13} />}
              Reject
            </button>
            <button
              id={`approve-${approval.approval_id}`}
              className="btn"
              disabled={loading}
              onClick={() => approveMut.mutate()}
              style={{ flex: 2, background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.3)', color: 'var(--color-success)' }}
            >
              {approveMut.isPending ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <CheckCircle size={13} />}
              Approve
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ApprovalsPage() {
  const [filter, setFilter] = useState<string>('pending');

  const { data: list, isLoading } = useQuery({
    queryKey: ['approvals', filter],
    queryFn: () => approvals.list(filter || undefined),
    refetchInterval: 10_000,
  });

  const FILTERS = ['all', 'pending', 'approved', 'rejected'];

  return (
    <AppLayout title="Approvals" subtitle="Review and act on workflow gates">
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Approval Queue</h1>
          <p>{list?.length ?? 0} {filter} approvals</p>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {FILTERS.map(f => (
            <button key={f} onClick={() => setFilter(f === 'all' ? '' : f)}
              className="btn"
              style={{
                padding: '6px 14px', fontSize: 12, fontWeight: 600,
                background: filter === (f === 'all' ? '' : f) ? 'rgba(99,102,241,0.15)' : 'var(--color-surface-2)',
                border: `1px solid ${filter === (f === 'all' ? '' : f) ? 'var(--color-primary)' : 'var(--color-border)'}`,
                color: filter === (f === 'all' ? '' : f) ? 'var(--color-primary-h)' : 'var(--color-text-2)',
              }}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-2)' }}>
          <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', display: 'block', margin: '0 auto 12px' }} />
          Loading approvals…
        </div>
      ) : list?.length ? (
        list.map(a => <ApprovalCard key={a.approval_id} approval={a} />)
      ) : (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <CheckCircle size={48} style={{ opacity: 0.15, display: 'block', margin: '0 auto 16px', color: 'var(--color-success)' }} />
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: 'var(--color-text)' }}>No {filter} approvals</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-2)' }}>
            All clear! Approvals appear here when workflows reach a manual gate.
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </AppLayout>
  );
}
