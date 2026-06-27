'use client';

import { useQuery } from '@tanstack/react-query';
import { DollarSign, Loader2 } from 'lucide-react';
import AppLayout from '../../components/AppLayout';
import { cost } from '../../lib/api';

export default function CostPage() {
  const { data: report, isLoading } = useQuery({
    queryKey: ['cost-report'],
    queryFn: () => cost.getReport(),
    refetchInterval: 60_000,
  });

  const COLORS = [
    'var(--color-primary)', 'var(--color-accent)', 'var(--color-success)',
    'var(--color-warning)', 'var(--color-danger)', '#a855f7',
  ];

  return (
    <AppLayout title="Cost Optimizer" subtitle="Token usage, compute and storage costs">
      <div className="section-header">
        <h1>Cost Optimization</h1>
        <p>Real-time cost tracking across all agents, tokens, and infrastructure</p>
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 80, color: 'var(--color-text-2)' }}>
          <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', display: 'block', margin: '0 auto 12px' }} />
          Loading cost report…
        </div>
      ) : report ? (
        <>
          {/* Summary cards */}
          <div className="stat-grid" style={{ marginBottom: 24 }}>
            <div className="stat-card">
              <div className="stat-icon amber"><DollarSign /></div>
              <div className="stat-value">${(report.total_cost_usd ?? 0).toFixed(2)}</div>
              <div className="stat-label">Total Cost (MTD)</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon indigo"><DollarSign /></div>
              <div className="stat-value">${(report.token_cost_usd ?? 0).toFixed(2)}</div>
              <div className="stat-label">LLM Token Cost</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon cyan"><DollarSign /></div>
              <div className="stat-value">${(report.compute_cost_usd ?? 0).toFixed(2)}</div>
              <div className="stat-label">Compute Cost</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon green"><DollarSign /></div>
              <div className="stat-value">{((report.total_tokens ?? 0) / 1000).toFixed(0)}K</div>
              <div className="stat-label">Total Tokens Used</div>
            </div>
          </div>

          {/* Breakdown */}
          <div className="grid-row cols-2">
            <div className="card">
              <div className="card-header">
                <div className="card-title">💰 Cost Breakdown</div>
              </div>
              {(report.breakdown ?? []).map((item, i) => (
                <div key={item.category} className="cost-row">
                  <div className="cost-label">{item.category}</div>
                  <div className="cost-bar-track">
                    <div className="cost-bar-fill" style={{ width: `${item.percentage ?? 0}%`, background: COLORS[i % COLORS.length] }} />
                  </div>
                  <div className="cost-amount">${(item.amount ?? 0).toFixed(2)}</div>
                </div>
              ))}
              {(!report.breakdown?.length) && (
                <p style={{ color: 'var(--color-text-2)', fontSize: 13 }}>No cost data available yet.</p>
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <div className="card-title">📊 Token Usage</div>
              </div>
              <div className="token-stats">
                <div className="token-stat">
                  <div className="token-stat-val" style={{ color: 'var(--color-primary-h)' }}>{((report.total_tokens ?? 0) / 1000).toFixed(0)}K</div>
                  <div className="token-stat-lbl">Total Tokens</div>
                </div>
                <div className="token-stat">
                  <div className="token-stat-val" style={{ color: 'var(--color-accent)' }}>{((report.input_tokens ?? 0) / 1000).toFixed(0)}K</div>
                  <div className="token-stat-lbl">Input Tokens</div>
                </div>
                <div className="token-stat">
                  <div className="token-stat-val" style={{ color: 'var(--color-success)' }}>{((report.output_tokens ?? 0) / 1000).toFixed(0)}K</div>
                  <div className="token-stat-lbl">Output Tokens</div>
                </div>
              </div>
              <div style={{ marginTop: 24, padding: 16, background: 'rgba(99,102,241,0.06)', borderRadius: 10, border: '1px solid rgba(99,102,241,0.12)' }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--color-text)' }}>Optimization Tips</div>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 12, color: 'var(--color-text-2)', lineHeight: 1.8 }}>
                  <li>✦ Enable prompt caching to reduce repeat token costs</li>
                  <li>✦ Use smaller models for low-complexity tasks</li>
                  <li>✦ Set per-project budget limits to cap spending</li>
                  <li>✦ Archive completed workflows to reduce storage</li>
                </ul>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <DollarSign size={48} style={{ opacity: 0.15, display: 'block', margin: '0 auto 16px', color: 'var(--color-warning)' }} />
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-text)', marginBottom: 8 }}>No cost data yet</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-2)' }}>Run a workflow to start tracking costs.</div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </AppLayout>
  );
}
