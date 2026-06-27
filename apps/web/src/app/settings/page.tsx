'use client';

import { getCurrentUser } from '../../lib/auth';
import { logout } from '../../lib/auth';
import AppLayout from '../../components/AppLayout';
import { useState } from 'react';
import { Save, Key, User, Bell, Shield } from 'lucide-react';

export default function SettingsPage() {
  const user = getCurrentUser();
  const [saved, setSaved] = useState(false);
  const [openAIKey, setOpenAIKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <AppLayout title="Settings" subtitle="Platform configuration">
      <div className="section-header">
        <h1>Settings</h1>
        <p>Manage your account, API keys, and platform configuration</p>
      </div>

      <div className="grid-row cols-2">
        {/* Account */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><User size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />Account</div>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>Username</label>
            <input value={user?.username ?? ''} readOnly
              style={{ width: '100%', padding: '9px 12px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text-2)', fontSize: 13, boxSizing: 'border-box', cursor: 'not-allowed' }} />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>Role</label>
            <input value={user?.role ?? ''} readOnly
              style={{ width: '100%', padding: '9px 12px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text-2)', fontSize: 13, boxSizing: 'border-box', cursor: 'not-allowed' }} />
          </div>
          <div style={{ paddingTop: 16, borderTop: '1px solid var(--color-border)' }}>
            <button onClick={() => logout()}
              style={{ padding: '8px 16px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 8, color: 'var(--color-danger)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
              Sign Out
            </button>
          </div>
        </div>

        {/* LLM Keys */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Key size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />LLM API Keys</div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-2)', marginBottom: 16, background: 'rgba(99,102,241,0.06)', padding: '10px 12px', borderRadius: 8, border: '1px solid rgba(99,102,241,0.12)' }}>
            Keys are stored in your backend <code style={{ color: 'var(--color-primary-h)' }}>.env</code> file. Add them there to enable real AI generation.
          </div>
          {[
            { label: 'OpenAI API Key', val: openAIKey, set: setOpenAIKey, ph: 'sk-...' },
            { label: 'Anthropic API Key', val: anthropicKey, set: setAnthropicKey, ph: 'sk-ant-...' },
            { label: 'Google Gemini Key', val: geminiKey, set: setGeminiKey, ph: 'AIza...' },
          ].map(f => (
            <div key={f.label} style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>{f.label}</label>
              <input type="password" value={f.val} onChange={e => f.set(e.target.value)} placeholder={f.ph}
                style={{ width: '100%', padding: '9px 12px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text)', fontSize: 13, boxSizing: 'border-box', outline: 'none' }} />
            </div>
          ))}
          <button onClick={handleSave} className="btn btn-primary" style={{ marginTop: 4 }}>
            <Save size={13} /> {saved ? 'Saved!' : 'Save Keys'}
          </button>
        </div>

        {/* Security */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Shield size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />Security</div>
          </div>
          {[
            { label: 'JWT Token Expiry', value: '60 minutes' },
            { label: 'Refresh Token Expiry', value: '7 days' },
            { label: 'Rate Limit', value: '100 req/min' },
            { label: 'CORS Origins', value: 'localhost:3000' },
            { label: 'Auth Algorithm', value: 'HS256' },
          ].map(r => (
            <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid rgba(99,132,255,0.06)', fontSize: 13 }}>
              <span style={{ color: 'var(--color-text-2)' }}>{r.label}</span>
              <span style={{ color: 'var(--color-text)', fontWeight: 600 }}>{r.value}</span>
            </div>
          ))}
        </div>

        {/* Platform Info */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Bell size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />Platform Info</div>
          </div>
          {[
            { label: 'Version',       value: 'v1.0.0' },
            { label: 'Milestones',    value: '18 complete ✓' },
            { label: 'Backend',       value: 'FastAPI + SQLAlchemy' },
            { label: 'Frontend',      value: 'Next.js 15' },
            { label: 'Orchestrator',  value: 'LangGraph' },
            { label: 'Agents',        value: 'CrewAI' },
            { label: 'Queue',         value: 'Kafka (configurable)' },
            { label: 'Cache',         value: 'Redis (configurable)' },
            { label: 'Database',      value: 'SQLite (dev) / PostgreSQL (prod)' },
          ].map(r => (
            <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid rgba(99,132,255,0.06)', fontSize: 13 }}>
              <span style={{ color: 'var(--color-text-2)' }}>{r.label}</span>
              <span style={{ color: 'var(--color-text)', fontWeight: 600 }}>{r.value}</span>
            </div>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
