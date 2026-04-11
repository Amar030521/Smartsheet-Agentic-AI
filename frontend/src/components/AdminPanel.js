import React, { useState, useEffect, useCallback } from 'react';

const BACKEND_URL = process.env.REACT_APP_API_URL || '';

function api(path, method = 'GET', body = null, token) {
  return fetch(`${BACKEND_URL}/api/v1/auth${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : null
  }).then(r => r.json());
}

const S = {
  overlay: { position:'fixed', inset:0, background:'rgba(0,0,0,0.5)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center' },
  panel: { background:'#fff', borderRadius:16, width:760, maxHeight:'88vh', overflow:'hidden', display:'flex', flexDirection:'column', boxShadow:'0 24px 80px rgba(0,0,0,0.2)' },
  header: { padding:'18px 24px', borderBottom:'1px solid #f0d5be', display:'flex', alignItems:'center', justifyContent:'space-between', flexShrink:0 },
  tab: (active) => ({ padding:'7px 18px', borderRadius:8, border:'none', cursor:'pointer', fontSize:12, fontWeight:700, background: active?'#d4651a':'#fff3ea', color: active?'#fff':'#b07a55' }),
  input: { width:'100%', padding:'10px 12px', border:'1.5px solid #f0d5be', borderRadius:8, fontSize:13, color:'#1a1a1a', boxSizing:'border-box', background:'#fdf8f5', outline:'none' },
  label: { fontSize:11, fontWeight:700, color:'#7a4f30', textTransform:'uppercase', letterSpacing:'0.06em', display:'block', marginBottom:6 },
  btn: (color, sm) => ({ padding: sm?'5px 12px':'9px 18px', borderRadius:8, border:'none', cursor:'pointer', fontSize: sm?11:13, fontWeight:700, background:color, color:'#fff' }),
};

// Field must be defined OUTSIDE AdminPanel — if defined inside, React treats it as a
// new component type on every render, unmounting/remounting the input and losing focus.
function Field({ label, children }) {
  return (
    <div style={{ marginBottom:14 }}>
      <label style={S.label}>{label}</label>
      {children}
    </div>
  );
}

export default function AdminPanel({ token, onClose }) {
  const [tab, setTab]           = useState('users');
  const [users, setUsers]       = useState([]);
  const [logs, setLogs]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [success, setSuccess]   = useState('');
  const [editUser, setEditUser] = useState(null);

  const [form, setForm] = useState({ name:'', email:'', password:'', smartsheet_token:'', is_admin:false });

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api('/users', 'GET', null, token);
      setUsers(data.users || []);
    } catch { setError('Failed to load users'); }
    finally { setLoading(false); }
  }, [token]);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api('/logs', 'GET', null, token);
      setLogs(data.logs || []);
    } catch { setError('Failed to load logs'); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    if (tab === 'users') loadUsers();
    else if (tab === 'logs') loadLogs();
  }, [tab, loadUsers, loadLogs]);

  const addUser = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      const res = await api('/users', 'POST', form, token);
      if (res.detail) { setError(res.detail); return; }
      setSuccess(`User ${form.email} created`);
      setForm({ name:'', email:'', password:'', smartsheet_token:'', is_admin:false });
      loadUsers(); setTab('users');
    } catch { setError('Failed to create user'); }
  };

  const saveEdit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    const updates = { name: editUser.name, is_active: editUser.is_active, is_admin: editUser.is_admin };
    if (editUser.smartsheet_token) updates.smartsheet_token = editUser.smartsheet_token;
    if (editUser.new_password && editUser.new_password.length >= 8) {
      await api(`/users/${editUser.id}/reset-password`, 'POST', { password: editUser.new_password }, token);
    }
    const res = await api(`/users/${editUser.id}`, 'PATCH', updates, token);
    if (res.detail) { setError(res.detail); return; }
    setSuccess('User updated');
    setEditUser(null);
    loadUsers();
  };

  const toggleActive = async (user) => {
    await api(`/users/${user.id}`, 'PATCH', { is_active: !user.is_active }, token);
    loadUsers();
  };

  const removeUser = async (user) => {
    if (!window.confirm(`Deactivate ${user.name}?`)) return;
    await api(`/users/${user.id}`, 'DELETE', null, token);
    loadUsers();
  };

  return (
    <div style={S.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={S.panel}>
        {/* Header */}
        <div style={S.header}>
          <div>
            <div style={{ fontSize:15, fontWeight:800, color:'#1a1a1a' }}>⚙️ Admin Panel</div>
            <div style={{ fontSize:11, color:'#b07a55', marginTop:2 }}>Manage users and monitor access</div>
          </div>
          <div style={{ display:'flex', gap:6, alignItems:'center' }}>
            {['users','add','logs'].map(t => (
              <button key={t} style={S.tab(tab===t)} onClick={() => { setTab(t); setEditUser(null); setError(''); setSuccess(''); }}>
                {t === 'users' ? '👥 Users' : t === 'add' ? '+ Add User' : '📋 Login Logs'}
              </button>
            ))}
            <button onClick={onClose} style={{ background:'none', border:'none', fontSize:20, cursor:'pointer', color:'#b07a55', padding:'0 4px' }}>×</button>
          </div>
        </div>

        {/* Alerts */}
        {(error||success) && (
          <div style={{ padding:'0 24px' }}>
            {error && <div style={{ background:'#fef2f2', border:'1px solid #fca5a5', borderRadius:8, padding:'10px 14px', margin:'12px 0', fontSize:13, color:'#991b1b' }}>⚠️ {error}</div>}
            {success && <div style={{ background:'#f0fdf4', border:'1px solid #86efac', borderRadius:8, padding:'10px 14px', margin:'12px 0', fontSize:13, color:'#166534' }}>✅ {success}</div>}
          </div>
        )}

        {/* Content */}
        <div style={{ flex:1, overflowY:'auto', padding:'0 24px 24px' }}>

          {/* USERS TAB */}
          {tab === 'users' && !editUser && (
            <>
              <div style={{ margin:'14px 0 10px', fontSize:13, color:'#7a4f30', fontWeight:600 }}>{users.length} user{users.length!==1?'s':''} registered</div>
              {loading ? <div style={{ textAlign:'center', padding:40, color:'#b07a55' }}>Loading...</div> : (
                <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
                  {users.map(u => (
                    <div key={u.id} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'12px 16px', border:'1px solid #f0d5be', borderRadius:10, background: u.is_active?'#fff':'#fafafa', opacity: u.is_active?1:0.65 }}>
                      <div>
                        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                          <span style={{ fontSize:13, fontWeight:700, color:'#1a1a1a' }}>{u.name}</span>
                          {u.is_admin && <span style={{ fontSize:10, background:'#d4651a', color:'#fff', padding:'2px 7px', borderRadius:10, fontWeight:700 }}>ADMIN</span>}
                          {!u.is_active && <span style={{ fontSize:10, background:'#94a3b8', color:'#fff', padding:'2px 7px', borderRadius:10, fontWeight:700 }}>INACTIVE</span>}
                        </div>
                        <div style={{ fontSize:12, color:'#7a4f30', marginTop:2 }}>{u.email}</div>
                        {u.last_login && <div style={{ fontSize:11, color:'#b07a55', marginTop:2 }}>Last login: {new Date(u.last_login).toLocaleString()}</div>}
                      </div>
                      <div style={{ display:'flex', gap:6 }}>
                        <button onClick={() => setEditUser({...u, new_password:'', smartsheet_token:''})} style={S.btn('#3b82f6', true)}>Edit</button>
                        <button onClick={() => toggleActive(u)} style={S.btn(u.is_active?'#f59e0b':'#10b981', true)}>{u.is_active?'Deactivate':'Activate'}</button>
                        <button onClick={() => removeUser(u)} style={S.btn('#ef4444', true)}>Remove</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* EDIT USER */}
          {tab === 'users' && editUser && (
            <form onSubmit={saveEdit} style={{ marginTop:20 }}>
              <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:20 }}>
                <button type="button" onClick={() => setEditUser(null)} style={{ background:'none', border:'none', cursor:'pointer', color:'#b07a55', fontSize:20 }}>←</button>
                <div style={{ fontSize:15, fontWeight:700, color:'#1a1a1a' }}>Edit: {editUser.email}</div>
              </div>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
                <Field label="Full Name">
                  <input style={S.input} value={editUser.name} onChange={e => setEditUser({...editUser, name:e.target.value})} required />
                </Field>
                <Field label="New Smartsheet API Token (leave blank to keep current)">
                  <input style={S.input} placeholder="Leave blank to keep existing token" value={editUser.smartsheet_token}
                    onChange={e => setEditUser({...editUser, smartsheet_token:e.target.value})} />
                </Field>
                <Field label="New Password (leave blank to keep current)">
                  <input style={S.input} type="password" placeholder="Min 8 chars — leave blank to keep" value={editUser.new_password}
                    onChange={e => setEditUser({...editUser, new_password:e.target.value})} minLength={editUser.new_password?8:0} />
                </Field>
                <div style={{ display:'flex', flexDirection:'column', gap:12, paddingTop:8 }}>
                  <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer', fontSize:13 }}>
                    <input type="checkbox" checked={editUser.is_admin} onChange={e => setEditUser({...editUser, is_admin:e.target.checked})} style={{ accentColor:'#d4651a' }} />
                    Grant admin access
                  </label>
                  <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer', fontSize:13 }}>
                    <input type="checkbox" checked={editUser.is_active} onChange={e => setEditUser({...editUser, is_active:e.target.checked})} style={{ accentColor:'#10b981' }} />
                    Account active
                  </label>
                </div>
              </div>
              <div style={{ display:'flex', gap:10, marginTop:20 }}>
                <button type="submit" style={S.btn('#d4651a')}>Save Changes</button>
                <button type="button" onClick={() => setEditUser(null)} style={S.btn('#94a3b8')}>Cancel</button>
              </div>
            </form>
          )}

          {/* ADD USER TAB */}
          {tab === 'add' && (
            <form onSubmit={addUser} style={{ marginTop:20 }}>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:14 }}>
                <Field label="Full Name"><input style={S.input} placeholder="Rahul Singh" value={form.name} onChange={e => setForm({...form,name:e.target.value})} required /></Field>
                <Field label="Email Address"><input style={S.input} type="email" placeholder="rahul@company.com" value={form.email} onChange={e => setForm({...form,email:e.target.value})} required /></Field>
                <Field label="Password"><input style={S.input} type="password" placeholder="Min 8 characters" value={form.password} onChange={e => setForm({...form,password:e.target.value})} required minLength={8} /></Field>
                <Field label="Smartsheet API Token"><input style={S.input} placeholder="Their personal Smartsheet token" value={form.smartsheet_token} onChange={e => setForm({...form,smartsheet_token:e.target.value})} required /></Field>
              </div>
              <label style={{ display:'flex', alignItems:'center', gap:10, fontSize:13, marginBottom:16, cursor:'pointer' }}>
                <input type="checkbox" checked={form.is_admin} onChange={e => setForm({...form,is_admin:e.target.checked})} style={{ accentColor:'#d4651a', width:16, height:16 }} />
                Grant admin access (can manage users and view login logs)
              </label>
              <div style={{ background:'#fff7f0', border:'1px solid #f0d5be', borderRadius:8, padding:'12px 16px', marginBottom:18, fontSize:12, color:'#7a4f30' }}>
                💡 The Smartsheet API token must be the user's own — from Smartsheet → Account → Personal Settings → API Access. Each user will only see their own Smartsheet data.
              </div>
              <button type="submit" style={S.btn('#d4651a')}>Create User</button>
            </form>
          )}

          {/* LOGIN LOGS TAB */}
          {tab === 'logs' && (
            <>
              <div style={{ margin:'14px 0 10px', fontSize:13, color:'#7a4f30', fontWeight:600 }}>{logs.length} login events</div>
              {loading ? <div style={{ textAlign:'center', padding:40, color:'#b07a55' }}>Loading...</div> : (
                <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                  {logs.length === 0 && <div style={{ color:'#b07a55', fontSize:13, padding:20, textAlign:'center' }}>No login logs yet. Logs are recorded after the login_logs table is created in Supabase.</div>}
                  {logs.map((log, i) => (
                    <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'10px 14px', border:'1px solid #f0d5be', borderRadius:8, background:'#fff' }}>
                      <div>
                        <div style={{ fontSize:13, fontWeight:600, color:'#1a1a1a' }}>{log.users?.name || 'Unknown'}</div>
                        <div style={{ fontSize:12, color:'#7a4f30' }}>{log.users?.email || log.user_id}</div>
                      </div>
                      <div style={{ textAlign:'right' }}>
                        <div style={{ fontSize:12, color:'#1a1a1a' }}>{new Date(log.logged_in_at).toLocaleString()}</div>
                        <div style={{ fontSize:11, color:'#b07a55' }}>IP: {log.ip_address}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}