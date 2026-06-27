'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Folder, X, Loader2 } from 'lucide-react';
import AppLayout from '../../components/AppLayout';
import { projects, type ProjectCreate } from '../../lib/api';

const TECH_PRESETS: Record<string, Record<string, string>> = {
  'Next.js + FastAPI':  { frontend: 'Next.js', backend: 'FastAPI', database: 'PostgreSQL', infra: 'Docker/K8s' },
  'React + Node.js':   { frontend: 'React',    backend: 'Node.js',  database: 'MongoDB',    infra: 'Docker' },
  'Vue + Django':      { frontend: 'Vue 3',    backend: 'Django',   database: 'PostgreSQL', infra: 'Heroku' },
  'Angular + Spring':  { frontend: 'Angular',  backend: 'Spring',   database: 'MySQL',      infra: 'AWS ECS' },
};

export default function ProjectsPage() {
  const qc = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<ProjectCreate>({
    name: '',
    description: '',
    tech_stack: TECH_PRESETS['Next.js + FastAPI'],
    repository_url: '',
    budget_usd_limit: 50,
  });
  const [preset, setPreset] = useState('Next.js + FastAPI');
  const [formError, setFormError] = useState('');

  const { data: list, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projects.list(0, 100),
  });

  const createMut = useMutation({
    mutationFn: (data: ProjectCreate) => projects.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] });
      setShowModal(false);
      setForm({ name: '', description: '', tech_stack: TECH_PRESETS['Next.js + FastAPI'], repository_url: '', budget_usd_limit: 50 });
      setFormError('');
    },
    onError: (err: any) => setFormError(err.detail ?? 'Failed to create project'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => projects.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });

  function handlePreset(p: string) {
    setPreset(p);
    setForm(f => ({ ...f, tech_stack: TECH_PRESETS[p] }));
  }

  return (
    <AppLayout title="Projects" subtitle="Manage your SDLC projects">
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Projects</h1>
          <p>{list?.length ?? 0} projects · Each project runs an autonomous 14-stage pipeline</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)} id="create-project-btn">
          <Plus size={14} /> New Project
        </button>
      </div>

      {/* Project Grid */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-2)' }}>
          <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 12px', display: 'block' }} />
          Loading projects…
        </div>
      ) : list?.length ? (
        <div className="grid-row cols-3">
          {list.map(p => (
            <div key={p.project_id} className="card" style={{ position: 'relative', cursor: 'pointer' }}
              onClick={() => window.location.href = `/projects/${p.project_id}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
                <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgba(99,102,241,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-primary-h)' }}>
                  <Folder size={18} />
                </div>
                <button
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-3)', padding: 4 }}
                  onClick={e => { e.stopPropagation(); deleteMut.mutate(p.project_id); }}
                  title="Delete project"
                >
                  <X size={14} />
                </button>
              </div>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--color-text)', marginBottom: 6 }}>{p.name}</div>
              {p.description && (
                <div style={{ fontSize: 12, color: 'var(--color-text-2)', marginBottom: 12, lineHeight: 1.5 }}>
                  {p.description.slice(0, 100)}{p.description.length > 100 ? '…' : ''}
                </div>
              )}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 14 }}>
                {Object.values(p.tech_stack).slice(0, 4).map((t: any) => (
                  <span key={t} className="badge badge-info">{t}</span>
                ))}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--color-text-2)' }}>
                <span>Budget: ${Number(p.budget_usd_limit).toFixed(0)}</span>
                <span>{new Date(p.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <Folder size={48} style={{ opacity: 0.15, display: 'block', margin: '0 auto 16px', color: 'var(--color-primary)' }} />
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: 'var(--color-text)' }}>No projects yet</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-2)', marginBottom: 24 }}>
            Create a project to kick off your first autonomous SDLC pipeline.
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={14} /> Create First Project
          </button>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: 24,
        }}
          onClick={e => e.target === e.currentTarget && setShowModal(false)}>
          <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 20,
            padding: 32,
            width: '100%', maxWidth: 540,
            maxHeight: '90vh', overflowY: 'auto',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700 }}>New Project</h2>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-2)' }}><X size={18} /></button>
            </div>

            {formError && (
              <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', color: 'var(--color-danger)', fontSize: 13, marginBottom: 16 }}>
                {formError}
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>Project Name *</label>
              <input id="project-name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Enterprise Order Routing"
                style={{ width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text)', fontSize: 14, outline: 'none', boxSizing: 'border-box' }} />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>Description</label>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                rows={3} placeholder="Brief description of the project…"
                style={{ width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text)', fontSize: 14, outline: 'none', resize: 'vertical', boxSizing: 'border-box', fontFamily: 'var(--font-sans)' }} />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 8 }}>Tech Stack Preset</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {Object.keys(TECH_PRESETS).map(p => (
                  <button key={p} onClick={() => handlePreset(p)}
                    style={{ padding: '5px 12px', borderRadius: 99, fontSize: 12, fontWeight: 600, cursor: 'pointer', border: '1px solid', borderColor: preset === p ? 'var(--color-primary)' : 'var(--color-border)', background: preset === p ? 'rgba(99,102,241,0.15)' : 'transparent', color: preset === p ? 'var(--color-primary-h)' : 'var(--color-text-2)', transition: 'all 0.15s' }}>
                    {p}
                  </button>
                ))}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                {Object.entries(form.tech_stack).map(([k, v]) => (
                  <span key={k} className="badge badge-info">{k}: {v as string}</span>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>Repository URL</label>
              <input value={form.repository_url ?? ''} onChange={e => setForm(f => ({ ...f, repository_url: e.target.value }))}
                placeholder="https://github.com/org/repo"
                style={{ width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text)', fontSize: 14, outline: 'none', boxSizing: 'border-box' }} />
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 6 }}>Budget Limit (USD)</label>
              <input type="number" value={form.budget_usd_limit} onChange={e => setForm(f => ({ ...f, budget_usd_limit: Number(e.target.value) }))}
                min={1} step={10}
                style={{ width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text)', fontSize: 14, outline: 'none', boxSizing: 'border-box' }} />
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setShowModal(false)}>Cancel</button>
              <button id="create-project-submit" className="btn btn-primary" style={{ flex: 2 }}
                disabled={createMut.isPending || !form.name.trim()}
                onClick={() => createMut.mutate(form)}>
                {createMut.isPending ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Plus size={14} />}
                {createMut.isPending ? 'Creating…' : 'Create Project'}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </AppLayout>
  );
}
