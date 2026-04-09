import { useState, useEffect, useCallback } from 'react';

const BACKEND_URL = process.env.REACT_APP_API_URL || '';

export function useChatSessions(getToken, user) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadSessions = useCallback(async () => {
    const token = getToken ? getToken() : null;
    if (!token || !user) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/sessions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (e) {
      console.warn('Failed to load sessions', e);
    } finally {
      setLoading(false);
    }
  }, [user?.email]);

  useEffect(() => {
    if (user) loadSessions();
    else setSessions([]);
  }, [user?.email]);

  const loadMessages = useCallback(async (sessionId) => {
    const token = getToken ? getToken() : null;
    if (!token) return [];
    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/sessions/${sessionId}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      return data.messages || [];
    } catch { return []; }
  }, []);

  const renameSession = useCallback(async (sessionId, title) => {
    const token = getToken ? getToken() : null;
    if (!token) return;
    await fetch(`${BACKEND_URL}/api/v1/sessions/${sessionId}/title`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    });
    setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, title } : s));
  }, []);

  const deleteSession = useCallback(async (sessionId) => {
    const token = getToken ? getToken() : null;
    if (!token) return;
    await fetch(`${BACKEND_URL}/api/v1/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    });
    setSessions(prev => prev.filter(s => s.id !== sessionId));
  }, []);

  return { sessions, loading, loadSessions, loadMessages, renameSession, deleteSession };
}
