import { useState, useEffect, useCallback } from 'react';

const TOKEN_KEY = 'smartsheet_agent_token';
const USER_KEY  = 'smartsheet_agent_user';
const BACKEND_URL = process.env.REACT_APP_API_URL || '';

export function useAuth() {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  // On mount — verify stored token
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);
    if (!stored || !storedUser) { setLoading(false); return; }
    // Verify token still valid
    fetch(`${BACKEND_URL}/api/v1/auth/verify`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${stored}` }
    }).then(r => {
      if (r.ok) setUser(JSON.parse(storedUser));
      else { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }
    }).catch(() => {
      localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY);
    }).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');
    const userData = { email: data.email, name: data.name, is_admin: data.is_admin, user_id: data.user_id };
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify(userData));
    // Clear old session so user starts fresh — prevents orphan session_id issues
    localStorage.removeItem('smartsheet_agent_session');
    setUser(userData);
    return userData;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    // Clear session key too so next user gets a fresh session
    localStorage.removeItem('smartsheet_agent_session');
    setUser(null);
  }, []);

  const getToken = useCallback(() => localStorage.getItem(TOKEN_KEY), []);

  return { user, loading, login, logout, getToken };
}