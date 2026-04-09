import React, { useState } from 'react';

export default function LoginPage({ onLogin }) {
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await onLogin(email.trim(), password);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', background: 'linear-gradient(135deg, #fff7f0 0%, #ffecd8 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Inter, sans-serif'
    }}>
      <div style={{
        background: '#fff', borderRadius: 20, padding: '48px 44px', width: 420,
        boxShadow: '0 20px 60px rgba(212,101,26,0.12)', border: '1px solid #f0d5be'
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            width: 56, height: 56, background: 'linear-gradient(135deg, #d4651a, #e8832a)',
            borderRadius: 14, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16, boxShadow: '0 8px 24px rgba(212,101,26,0.3)'
          }}>
            <span style={{ fontSize: 26 }}>📊</span>
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#1a1a1a', letterSpacing: '-0.02em' }}>
            Smartsheet AI Agent
          </div>
          <div style={{ fontSize: 13, color: '#b07a55', marginTop: 6 }}>
            Sign in to access your workspace
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 18 }}>
            <label style={{ fontSize: 12, fontWeight: 700, color: '#7a4f30', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>
              Email address
            </label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com" required autoFocus
              style={{
                width: '100%', padding: '12px 14px', border: '1.5px solid #f0d5be',
                borderRadius: 10, fontSize: 14, color: '#1a1a1a', outline: 'none',
                boxSizing: 'border-box', background: '#fdf8f5',
                transition: 'border-color 0.2s'
              }}
              onFocus={e => e.target.style.borderColor = '#d4651a'}
              onBlur={e => e.target.style.borderColor = '#f0d5be'}
            />
          </div>

          <div style={{ marginBottom: 28 }}>
            <label style={{ fontSize: 12, fontWeight: 700, color: '#7a4f30', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>
              Password
            </label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••" required
              style={{
                width: '100%', padding: '12px 14px', border: '1.5px solid #f0d5be',
                borderRadius: 10, fontSize: 14, color: '#1a1a1a', outline: 'none',
                boxSizing: 'border-box', background: '#fdf8f5',
                transition: 'border-color 0.2s'
              }}
              onFocus={e => e.target.style.borderColor = '#d4651a'}
              onBlur={e => e.target.style.borderColor = '#f0d5be'}
            />
          </div>

          {error && (
            <div style={{
              background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8,
              padding: '10px 14px', marginBottom: 20, fontSize: 13, color: '#991b1b',
              display: 'flex', gap: 8, alignItems: 'center'
            }}>
              <span>⚠️</span> {error}
            </div>
          )}

          <button
            type="submit" disabled={loading}
            style={{
              width: '100%', padding: '13px', background: loading ? '#e8c4a0' : 'linear-gradient(135deg, #d4651a, #e8832a)',
              color: '#fff', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer', letterSpacing: '-0.01em',
              boxShadow: loading ? 'none' : '0 4px 14px rgba(212,101,26,0.4)',
              transition: 'all 0.2s'
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: 24, fontSize: 12, color: '#b07a55' }}>
          Access is restricted to authorised users only.
          <br />Contact your administrator to get access.
        </div>
      </div>
    </div>
  );
}
