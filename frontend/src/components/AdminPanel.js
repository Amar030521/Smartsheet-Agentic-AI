import React, { useState, useEffect, useCallback } from 'react';

const BACKEND_URL = process.env.REACT_APP_API_URL || '';

function api(path, method = 'GET', body = null, token) {
  return fetch(`${BACKEND_URL}/api/v1/auth${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : null
  }).then(r => r.json());
}

export default function AdminPanel({ token, onClose }) {
  const [users, setUsers]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [tab, setTab]           = useState('users'); // 'users' | 'add'
  const [error, setError]       = useState('');
  const [success, setSuccess]   = useState('');

  // Add user form
  const [form, setForm] = useState({ name: '', email: '', password: '', smartsheet_token: '', is_admin: false });

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api('/users', 'GET', null, token);
      setUsers(data.users || []);
    } catch { setError('Failed to load users'); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const addUser = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      const res = await api('/users', 'POST', form, token);
      if (res.detail) { setError(res.detail); return; }
      setSuccess(`User ${form.email} created successfully`);
      setForm({ name: '', email: '', password: '', smartsheet_token: '', is_admin: false });
      loadUsers();
      setTab('users');
    } catch { setError('Failed to create user'); }
  };

  const toggleActive = async (user) => {
    await api(`/users/${user.id}`, 'PATCH', { is_active: !user.is_active }, token);
    loadUsers();
  };

  const deleteUser = async (user) => {
    if (!window.confirm(`Deactivate ${user.name}?`)) return;
    await api(`/users/${user.id}`, 'DELETE', null, token);
    loadUsers();
  };

  const S = {
    overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' },
    panel: { background: '#fff', borderRadius: 16, width: 720, maxHeight: '85vh', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 24px 80px rgba(0,0,0,0.2)' },
    header: { padding: '20px 24px', borderBottom: '1px solid #f0d5be', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
    tab: (active) => ({ padding: '8px 20px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 700, background: active ? '#d4651a' : '#fff3ea', color: active ? '#fff' : '#b07a55' }),
    input: { width: '100%', padding: '10px 12px', border: '1.5px solid #f0d5be', borderRadius: 8, fontSize: 13, color: '#1a1a1a', boxSizing: 'border-box', background: '#fdf8f5', outline: 'none' },
    label: { fontSize: 11, fontWeight: 700, color: '#7a4f30', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 },
    btn: (color) => ({ padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 700, background: color, color: '#fff' }),
  };

  return (
    <div style={S.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={S.panel}>
        {/* Header */}
        <div style={S.header}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, color: '#1a1a1a' }}>⚙️ Admin Panel</div>
            <div style={{ fontSize: 12, color: '#b07a55', marginTop: 2 }}>Manage users and access</div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button style={S.tab(tab === 'users')} onClick={() => setTab('users')}>Users</button>
            <button style={S.tab(tab === 'add')} onClick={() => setTab('add')}>+ Add User</button>
            <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#b07a55', padding: '0 4px' }}>×</button>
          </div>
        </div>

        {/* Alerts */}
        <div style={{ padding: '0 24px' }}>
          {error && <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', margin: '12px 0', fontSize: 13, color: '#991b1b' }}>⚠️ {error}</div>}
          {success && <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: '10px 14px', margin: '12px 0', fontSize: 13, color: '#166534' }}>✅ {success}</div>}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 24px 24px' }}>
          {tab === 'users' && (
            <>
              <div style={{ marginTop: 16, marginBottom: 12, fontSize: 13, color: '#7a4f30', fontWeight: 600 }}>
                {users.length} user{users.length !== 1 ? 's' : ''} registered
              </div>
              {loading ? (
                <div style={{ textAlign: 'center', padding: 40, color: '#b07a55' }}>Loading users...</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {users.map(u => (
                    <div key={u.id} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '12px 16px', border: '1px solid #f0d5be', borderRadius: 10,
                      background: u.is_active ? '#fff' : '#fafafa', opacity: u.is_active ? 1 : 0.6
                    }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: '#1a1a1a' }}>{u.name}</span>
                          {u.is_admin && <span style={{ fontSize: 10, background: '#d4651a', color: '#fff', padding: '2px 7px', borderRadius: 10, fontWeight: 700 }}>ADMIN</span>}
                          {!u.is_active && <span style={{ fontSize: 10, background: '#94a3b8', color: '#fff', padding: '2px 7px', borderRadius: 10, fontWeight: 700 }}>INACTIVE</span>}
                        </div>
                        <div style={{ fontSize: 12, color: '#7a4f30', marginTop: 2 }}>{u.email}</div>
                        {u.last_login && <div style={{ fontSize: 11, color: '#b07a55', marginTop: 2 }}>Last login: {new Date(u.last_login).toLocaleDateString()}</div>}
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button onClick={() => toggleActive(u)} style={S.btn(u.is_active ? '#f59e0b' : '#10b981')}>
                          {u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button onClick={() => deleteUser(u)} style={S.btn('#ef4444')}>Remove</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === 'add' && (
            <form onSubmit={addUser} style={{ marginTop: 20 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                <div>
                  <label style={S.label}>Full Name</label>
                  <input style={S.input} placeholder="Rahul Singh" value={form.name}
                    onChange={e => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div>
                  <label style={S.label}>Email Address</label>
                  <input style={S.input} type="email" placeholder="rahul@company.com" value={form.email}
                    onChange={e => setForm({ ...form, email: e.target.value })} required />
                </div>
                <div>
                  <label style={S.label}>Password</label>
                  <input style={S.input} type="password" placeholder="Min 8 characters" value={form.password}
                    onChange={e => setForm({ ...form, password: e.target.value })} required minLength={8} />
                </div>
                <div>
                  <label style={S.label}>Smartsheet API Token</label>
                  <input style={S.input} placeholder="Their personal Smartsheet token" value={form.smartsheet_token}
                    onChange={e => setForm({ ...form, smartsheet_token: e.target.value })} required />
                </div>
              </div>
              <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 10 }}>
                <input type="checkbox" id="is_admin" checked={form.is_admin}
                  onChange={e => setForm({ ...form, is_admin: e.target.checked })}
                  style={{ width: 16, height: 16, accentColor: '#d4651a' }} />
                <label htmlFor="is_admin" style={{ fontSize: 13, color: '#1a1a1a', cursor: 'pointer' }}>
                  Grant admin access (can manage users)
                </label>
              </div>
              <div style={{ background: '#fff7f0', border: '1px solid #f0d5be', borderRadius: 8, padding: '12px 16px', marginBottom: 20, fontSize: 12, color: '#7a4f30' }}>
                💡 The Smartsheet API token must belong to the user's own Smartsheet account. They can generate it from: Smartsheet → Account → Personal Settings → API Access
              </div>
              <button type="submit" style={{ ...S.btn('#d4651a'), padding: '12px 28px', fontSize: 14 }}>
                Create User
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
