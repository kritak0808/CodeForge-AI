'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Shield, Key, FileText, Loader2, Plus, Trash2, Copy, Check, AlertCircle } from 'lucide-react';
import AppLayout from '../../components/AppLayout';
import { enterprise } from '../../lib/api';

export default function EnterprisePage() {
  const queryClient = useQueryClient();
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [keyName, setKeyName] = useState('');
  const [createdPlainKey, setCreatedPlainKey] = useState<string | null>(null);

  // Queries
  const { data: keys, isLoading: keysLoading, error: keysError } = useQuery({
    queryKey: ['enterprise-keys'],
    queryFn: () => enterprise.listKeys(),
    refetchInterval: 15_000,
  });

  const { data: auditEvents, isLoading: auditLoading } = useQuery({
    queryKey: ['enterprise-audit'],
    queryFn: () => enterprise.listAuditEvents(0, 100),
    refetchInterval: 30_000,
  });

  // Mutations
  const createKeyMutation = useMutation({
    mutationFn: (name: string) => enterprise.createKey({ name }),
    onSuccess: (data) => {
      setKeyName('');
      setCreatedPlainKey(data.plain_key);
      queryClient.invalidateQueries({ queryKey: ['enterprise-keys'] });
    },
  });

  const revokeKeyMutation = useMutation({
    mutationFn: (id: string) => enterprise.revokeKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['enterprise-keys'] });
    },
  });

  function handleCreateKey(e: React.FormEvent) {
    e.preventDefault();
    if (!keyName.trim()) return;
    createKeyMutation.mutate(keyName.trim());
  }

  function handleCopy(text: string, id: string) {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  return (
    <AppLayout title="Enterprise Suite" subtitle="API Keys, Security Auditing and Governance">
      <div className="section-header">
        <h1>Enterprise Suite</h1>
        <p>Manage infrastructure credentials, access logs, and security compliance policies</p>
      </div>

      <div className="grid-row cols-2" style={{ gap: 24, marginBottom: 24 }}>
        {/* API Keys Panel */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">🔑 API Credentials</div>
              <div className="card-subtitle">Generate and manage application tokens</div>
            </div>
          </div>

          <form onSubmit={handleCreateKey} style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            <input
              type="text"
              placeholder="Key Name (e.g. CI/CD pipeline)"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              disabled={createKeyMutation.isPending}
              style={{
                flex: 1,
                padding: '10px 14px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(99,132,255,0.18)',
                borderRadius: 10,
                color: 'var(--color-text)',
                fontSize: 14,
                outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={createKeyMutation.isPending || !keyName.trim()}
              style={{
                padding: '10px 16px',
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                border: 'none',
                borderRadius: 10,
                color: '#fff',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              {createKeyMutation.isPending ? <Loader2 size={16} style={{ animation: 'spin 1s linear' }} /> : <Plus size={16} />}
              Generate
            </button>
          </form>

          {createdPlainKey && (
            <div style={{
              background: 'rgba(6,182,212,0.1)',
              border: '1px solid rgba(6,182,212,0.3)',
              borderRadius: 10,
              padding: 16,
              marginBottom: 20,
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#22d3ee', marginBottom: 6 }}>Key Created Successfully!</div>
              <div style={{ fontSize: 12, color: 'var(--color-text-2)', marginBottom: 12 }}>
                Copy this key now. It will not be shown again for security reasons.
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <code style={{
                  flex: 1,
                  background: 'rgba(0,0,0,0.3)',
                  padding: '8px 12px',
                  borderRadius: 6,
                  fontSize: 12,
                  color: '#22d3ee',
                  wordBreak: 'break-all',
                }}>{createdPlainKey}</code>
                <button
                  onClick={() => handleCopy(createdPlainKey, 'plain')}
                  style={{
                    background: 'rgba(255,255,255,0.06)',
                    border: 'none',
                    padding: 8,
                    borderRadius: 6,
                    cursor: 'pointer',
                    color: 'var(--color-text)',
                  }}
                >
                  {copiedId === 'plain' ? <Check size={16} color="#10b981" /> : <Copy size={16} />}
                </button>
              </div>
            </div>
          )}

          {keysLoading ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto' }} />
            </div>
          ) : keys?.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Prefix</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {keys.map((k: any) => (
                    <tr key={k.api_key_id}>
                      <td style={{ fontWeight: 600 }}>{k.name}</td>
                      <td><code style={{ fontSize: 12 }}>{k.prefix}...</code></td>
                      <td>
                        <span className={`badge badge-${k.is_active ? 'success' : 'danger'}`}>
                          {k.is_active ? 'Active' : 'Revoked'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {k.is_active && (
                          <button
                            onClick={() => revokeKeyMutation.mutate(k.api_key_id)}
                            disabled={revokeKeyMutation.isPending}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: 'var(--color-danger)',
                              cursor: 'pointer',
                              padding: 4,
                            }}
                            title="Revoke Key"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-2)' }}>
              No API Keys found. Generate one to get started.
            </div>
          )}
        </div>

        {/* Feature Governance Info */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div className="card-header">
              <div>
                <div className="card-title">🛡️ Policy & Governance</div>
                <div className="card-subtitle">Compliance metrics and feature flags</div>
              </div>
            </div>
            <div style={{ fontSize: 13, color: 'var(--color-text-2)', lineHeight: 1.8 }}>
              <div style={{ marginBottom: 14 }}>
                <strong>SOC2 Compliance</strong>: Enforced by automatic audit logging of all credential creation, workflow triggers, and manual approvals.
              </div>
              <div style={{ marginBottom: 14 }}>
                <strong>Data Retention</strong>: Artifact storage policy set to 90 days. Run execution steps persist database changes dynamically to checkpoints.
              </div>
              <div>
                <strong>Identity Control</strong>: RBAC roles enforced by OAuth2 Bearer Tokens (JWT). Admin and developer roles verify specific permission scopes.
              </div>
            </div>
          </div>
          <div style={{
            background: 'rgba(99,102,241,0.06)',
            padding: 16,
            borderRadius: 12,
            border: '1px solid rgba(99,102,241,0.15)',
            marginTop: 16,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, fontWeight: 700, color: 'var(--color-text)' }}>
              <Shield size={18} style={{ color: 'var(--color-primary-h)' }} />
              Enterprise Security Mode: Active
            </div>
            <div style={{ fontSize: 11, color: 'var(--color-text-3)', marginTop: 4 }}>
              SSL/TLS encryption, argon2 password hashing, feature flag rotation, and Kafka message signing active.
            </div>
          </div>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="card" style={{ marginTop: 24 }}>
        <div className="card-header">
          <div>
            <div className="card-title">📄 Platform Audit Event Logs</div>
            <div className="card-subtitle">Complete log of all administrative actions</div>
          </div>
        </div>

        {auditLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', margin: '0 auto' }} />
          </div>
        ) : auditEvents?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>User ID</th>
                  <th>IP Address</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {auditEvents.map((evt: any) => (
                  <tr key={evt.audit_event_id}>
                    <td><code style={{ color: 'var(--color-primary-h)', fontWeight: 600 }}>{evt.action}</code></td>
                    <td><span style={{ fontSize: 12, color: 'var(--color-text-2)' }}>{evt.resource}</span></td>
                    <td className="mono" style={{ fontSize: 12 }}>{evt.user_id ? evt.user_id.slice(0, 8) + '...' : 'System'}</td>
                    <td className="mono" style={{ fontSize: 12 }}>{evt.ip_address || '—'}</td>
                    <td className="mono" style={{ fontSize: 12 }}>{new Date(evt.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--color-text-2)' }}>
            No audit logs found.
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </AppLayout>
  );
}
