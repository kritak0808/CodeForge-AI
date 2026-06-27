'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Cpu, Eye, EyeOff, Loader2 } from 'lucide-react';
import { auth, setTokens } from '../../lib/api';
import { ApiError } from '../../lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        // Register user first
        await auth.register({ username, email, password, role: 'developer' });
      }
      // Auth / login to get tokens
      const data = await auth.login(username, password);
      setTokens(data.access_token, data.refresh_token);
      // Also persist in cookie so middleware can read it (edge runtime)
      document.cookie = `cf_access_token=${data.access_token}; path=/; max-age=${data.expires_in}; SameSite=Lax`;
      router.push('/');
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Connection or validation error. Is the backend running?');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--color-bg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      backgroundImage: 'radial-gradient(ellipse at 50% 0%, rgba(99,102,241,0.18) 0%, transparent 60%)',
    }}>
      <div style={{ width: '100%', maxWidth: 420 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 30 }}>
          <div style={{
            width: 56, height: 56,
            borderRadius: 14,
            background: 'linear-gradient(135deg,#6366f1 0%,#8b5cf6 50%,#06b6d4 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 0 40px rgba(99,102,241,0.35)',
          }}>
            <Cpu size={28} color="#fff" />
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: -0.5, color: 'var(--color-text)', marginBottom: 6 }}>
            CodeForge AI
          </h1>
          <p style={{ color: 'var(--color-text-2)', fontSize: 14 }}>
            {isRegister ? 'Create an account to start building' : 'Autonomous SDLC Platform — Sign in to continue'}
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: 'linear-gradient(145deg,rgba(26,34,53,0.95),rgba(17,24,39,0.98))',
          border: '1px solid rgba(99,132,255,0.14)',
          borderRadius: 20,
          padding: 32,
          boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        }}>
          <form onSubmit={handleSubmit}>
            {/* Username */}
            <div style={{ marginBottom: 18 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 8 }}>
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="admin"
                required
                autoComplete="username"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(99,132,255,0.18)',
                  borderRadius: 10,
                  color: 'var(--color-text)',
                  fontSize: 14,
                  outline: 'none',
                  transition: 'border-color 0.18s',
                  boxSizing: 'border-box',
                }}
                onFocus={e => (e.target.style.borderColor = 'rgba(99,102,241,0.6)')}
                onBlur={e => (e.target.style.borderColor = 'rgba(99,132,255,0.18)')}
              />
            </div>

            {/* Email (only on register) */}
            {isRegister && (
              <div style={{ marginBottom: 18 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 8 }}>
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  required
                  autoComplete="email"
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(99,132,255,0.18)',
                    borderRadius: 10,
                    color: 'var(--color-text)',
                    fontSize: 14,
                    outline: 'none',
                    transition: 'border-color 0.18s',
                    boxSizing: 'border-box',
                  }}
                  onFocus={e => (e.target.style.borderColor = 'rgba(99,102,241,0.6)')}
                  onBlur={e => (e.target.style.borderColor = 'rgba(99,132,255,0.18)')}
                />
              </div>
            )}

            {/* Password */}
            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--color-text-2)', marginBottom: 8 }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  autoComplete="current-password"
                  style={{
                    width: '100%',
                    padding: '10px 40px 10px 14px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(99,132,255,0.18)',
                    borderRadius: 10,
                    color: 'var(--color-text)',
                    fontSize: 14,
                    outline: 'none',
                    transition: 'border-color 0.18s',
                    boxSizing: 'border-box',
                  }}
                  onFocus={e => (e.target.style.borderColor = 'rgba(99,102,241,0.6)')}
                  onBlur={e => (e.target.style.borderColor = 'rgba(99,132,255,0.18)')}
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(v => !v)}
                  style={{
                    position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--color-text-3)',
                    padding: 0, display: 'flex', alignItems: 'center',
                  }}
                >
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div style={{
                background: 'rgba(239,68,68,0.1)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: 13,
                color: 'var(--color-danger)',
                marginBottom: 18,
              }}>
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              id="login-submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '11px 20px',
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6 50%,#06b6d4)',
                border: 'none',
                borderRadius: 10,
                color: '#fff',
                fontSize: 14,
                fontWeight: 700,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                transition: 'all 0.18s',
                boxShadow: '0 4px 14px rgba(99,102,241,0.35)',
              }}
            >
              {loading && <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />}
              {loading ? (isRegister ? 'Creating Account…' : 'Signing in…') : (isRegister ? 'Create Account' : 'Sign In')}
            </button>
          </form>

          {/* Switch flow */}
          <p style={{ textAlign: 'center', marginTop: 18, fontSize: 13, color: 'var(--color-text-2)' }}>
            {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button
              onClick={() => {
                setIsRegister(!isRegister);
                setError('');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-primary-h)',
                cursor: 'pointer',
                fontWeight: 600,
                textDecoration: 'underline',
                padding: 0,
              }}
            >
              {isRegister ? 'Sign In' : 'Register'}
            </button>
          </p>

          {/* Hint */}
          {!isRegister && (
            <p style={{ textAlign: 'center', marginTop: 20, fontSize: 12, color: 'var(--color-text-3)' }}>
              Default credentials: <code style={{ color: 'var(--color-primary-h)' }}>admin</code> / <code style={{ color: 'var(--color-primary-h)' }}>admin123</code>
            </p>
          )}
        </div>

        <p style={{ textAlign: 'center', marginTop: 24, fontSize: 12, color: 'var(--color-text-3)' }}>
          CodeForge AI v1.0.0 · SDLC Orchestration Engine
        </p>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
