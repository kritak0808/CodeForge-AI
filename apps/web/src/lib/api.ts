// ─── Typed API Client ────────────────────────────────────────────────────────
// All requests go through this module so auth headers are automatically injected.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const API_BASE = `${BASE_URL}/api/v1`;

// ── Token helpers ─────────────────────────────────────────────────────────────
export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('cf_access_token');
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem('cf_access_token', access);
  localStorage.setItem('cf_refresh_token', refresh);
}

export function clearTokens() {
  localStorage.removeItem('cf_access_token');
  localStorage.removeItem('cf_refresh_token');
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('cf_refresh_token');
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────
interface ApiOptions extends RequestInit {
  skipAuth?: boolean;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public code?: string
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { skipAuth, ...init } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string>),
  };

  if (!skipAuth) {
    const token = getAccessToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  // Token expired — try refresh once
  if (res.status === 401 && !skipAuth) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${getAccessToken()}`;
      const retry = await fetch(`${API_BASE}${path}`, { ...init, headers });
      return parseResponse<T>(retry);
    } else {
      clearTokens();
      if (typeof window !== 'undefined') window.location.href = '/login';
      throw new ApiError(401, 'Session expired');
    }
  }

  return parseResponse<T>(res);
}

async function parseResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let body: any;
  try {
    body = JSON.parse(text);
  } catch {
    body = { detail: text };
  }

  if (!res.ok) {
    const detail =
      body?.error?.message ?? body?.detail ?? `HTTP ${res.status}`;
    const code = body?.error?.code;
    throw new ApiError(res.status, detail, code);
  }

  // Unwrap { success, data, error } envelope
  return (body?.data !== undefined ? body.data : body) as T;
}

async function tryRefreshToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const body = await res.json();
    const data = body?.data ?? body;
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserOut {
  user_id: string;
  username: string;
  email: string;
  role: string;
  is_verified: boolean;
  created_at: string;
}

export const auth = {
  login: (username: string, password: string) =>
    apiFetch<LoginResponse>('/auth/login', {
      method: 'POST',
      skipAuth: true,
      body: JSON.stringify({ username, password }),
    }),
  register: (data: { username: string; email: string; password: string; role?: string }) =>
    apiFetch<UserOut>('/auth/register', {
      method: 'POST',
      skipAuth: true,
      body: JSON.stringify(data),
    }),
  logout: (access_token: string, refresh_token: string) =>
    apiFetch<void>('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ access_token, refresh_token }),
    }),
};

// ── Health ────────────────────────────────────────────────────────────────────
export interface HealthStatus {
  status: string;
  database: string;
  redis: string;
  kafka: string;
  version: string;
}

export const health = {
  check: () => apiFetch<HealthStatus>('/health'),
};

// ── Projects ──────────────────────────────────────────────────────────────────
export interface Project {
  project_id: string;
  user_id: string;
  name: string;
  description?: string;
  tech_stack: Record<string, any>;
  repository_url?: string;
  budget_usd_limit: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  tech_stack: Record<string, any>;
  repository_url?: string;
  budget_usd_limit?: number;
}

export const projects = {
  list: (skip = 0, limit = 50) =>
    apiFetch<Project[]>(`/projects?skip=${skip}&limit=${limit}`),
  get: (id: string) =>
    apiFetch<Project>(`/projects/${id}`),
  create: (data: ProjectCreate) =>
    apiFetch<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<ProjectCreate>) =>
    apiFetch<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) =>
    apiFetch<void>(`/projects/${id}`, { method: 'DELETE' }),
};

// ── Workflows ─────────────────────────────────────────────────────────────────
export interface Workflow {
  workflow_id: string;
  project_id: string;
  user_id: string;
  status: string;
  current_state: string;
  tasks_completed: number;
  tasks_total: number;
  metadata_json?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreate {
  project_id: string;
  requirements?: string;
}

export const workflows = {
  list: (projectId?: string, skip = 0, limit = 50) => {
    const qs = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (projectId) qs.set('project_id', projectId);
    return apiFetch<Workflow[]>(`/workflows?${qs}`);
  },
  get: (id: string) => apiFetch<Workflow>(`/workflows/${id}`),
  create: (data: WorkflowCreate) =>
    apiFetch<Workflow>('/workflows', { method: 'POST', body: JSON.stringify(data) }),
  getStages: (id: string) =>
    apiFetch<any[]>(`/workflows/${id}/stages`),
};

// ── Approvals ─────────────────────────────────────────────────────────────────
export interface Approval {
  approval_id: string;
  workflow_id: string;
  approval_type: string;
  status: string;
  requested_at: string;
  decided_at?: string;
  notes?: string;
}

export const approvals = {
  list: (status?: string) => {
    const qs = status ? `?status=${status}` : '';
    return apiFetch<Approval[]>(`/approvals${qs}`);
  },
  approve: (id: string, notes?: string) =>
    apiFetch<Approval>(`/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
  reject: (id: string, notes?: string) =>
    apiFetch<Approval>(`/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
};

// ── Cost ──────────────────────────────────────────────────────────────────────
export interface CostReport {
  total_cost_usd: number;
  token_cost_usd: number;
  compute_cost_usd: number;
  storage_cost_usd: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  breakdown: Array<{ category: string; amount: number; percentage: number }>;
}

export const cost = {
  getReport: (projectId?: string) => {
    const qs = projectId ? `?project_id=${projectId}` : '';
    return apiFetch<CostReport>(`/cost/report${qs}`);
  },
};

// ── Observability ─────────────────────────────────────────────────────────────
export interface AgentHealth {
  agent_id: string;
  agent_type: string;
  status: string;
  last_heartbeat: string;
  tasks_completed: number;
  tasks_failed: number;
  avg_duration_ms: number;
}

export const observability = {
  agents: () => apiFetch<AgentHealth[]>('/observability/agents'),
  metrics: () => apiFetch<Record<string, any>>('/observability/metrics'),
  generate: (projectId: string, workflowId: string) =>
    apiFetch<any>('/observability/generate', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, workflow_id: workflowId }),
    }),
  getGeneration: (id: string) =>
    apiFetch<any>(`/observability/generations/${id}`),
  regenerate: (id: string, reason?: string) =>
    apiFetch<any>(`/observability/generations/${id}/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
};

// ── Enterprise (stats) ────────────────────────────────────────────────────────
export interface PlatformStats {
  total_projects: number;
  total_workflows: number;
  workflows_completed: number;
  workflows_active: number;
  total_users: number;
  pending_approvals: number;
}

export const enterprise = {
  stats: () => apiFetch<PlatformStats>('/enterprise/stats'),
  listKeys: () => apiFetch<any[]>('/api-keys'),
  createKey: (data: { name: string; expires_days?: number }) =>
    apiFetch<any>('/api-keys', { method: 'POST', body: JSON.stringify(data) }),
  revokeKey: (id: string) =>
    apiFetch<any>(`/api-keys/${id}`, { method: 'DELETE' }),
  listAuditEvents: (skip = 0, limit = 100) =>
    apiFetch<any[]>(`/audit-events?skip=${skip}&limit=${limit}`),
  createFlag: (data: { name: string; is_enabled: boolean; rules_json?: any }) =>
    apiFetch<any>('/feature-flags', { method: 'POST', body: JSON.stringify(data) }),
  checkFlagActive: (name: string) =>
    apiFetch<any>(`/feature-flags/${name}/active`),
};
