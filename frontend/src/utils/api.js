import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_API_URL || '';
const TOKEN_KEY = 'smartsheet_agent_token';

const api = axios.create({
  baseURL: `${BACKEND_URL}/api/v1`,
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' }
});

// Attach JWT to every request automatically
api.interceptors.request.use(config => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error normalization
api.interceptors.response.use(
  res => res,
  err => {
    const message = err.response?.data?.detail
      || err.response?.data?.error
      || err.message
      || 'Unknown error';
    return Promise.reject(new Error(message));
  }
);

export const sendMessage = async (message, sessionId, voiceInput = false) => {
  const { data } = await api.post('/chat', {
    message,
    session_id: sessionId,
    voice_input: voiceInput
  });
  return data;
};

/**
 * Streaming version — calls /chat/stream and yields real-time events.
 * onEvent(event) is called for each SSE event: { type: "status"|"tool"|"done"|"error" }
 * Falls back to regular /chat endpoint if stream fails or returns null.
 */
export const sendMessageStream = async (message, sessionId, voiceInput = false, onEvent) => {
  const token = localStorage.getItem(TOKEN_KEY);

  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ message, session_id: sessionId, voice_input: voiceInput })
    });

    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalPayload = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'done') {
              finalPayload = event.payload;
            }
            if (onEvent) onEvent(event);
          } catch (e) {
            // ignore malformed lines
          }
        }
        // heartbeat lines (": heartbeat") are ignored automatically
      }
    }

    // If stream completed but no done event received (connection dropped mid-stream),
    // fall back to the regular /chat endpoint to get the response
    if (!finalPayload) {
      console.warn('Stream ended without done event — falling back to /chat');
      if (onEvent) onEvent({ type: 'status', text: 'Finalising response...', icon: '✍️' });
      const { data } = await api.post('/chat', {
        message,
        session_id: sessionId,
        voice_input: voiceInput
      });
      return data;
    }

    return finalPayload;

  } catch (err) {
    // Stream failed entirely — fall back to regular /chat
    console.warn('Stream failed, falling back to /chat:', err.message);
    if (onEvent) onEvent({ type: 'status', text: 'Reconnecting...', icon: '🔄' });
    const { data } = await api.post('/chat', {
      message,
      session_id: sessionId,
      voice_input: voiceInput
    });
    return data;
  }
};

export const clearSession = async (sessionId) => {
  const { data } = await api.delete(`/session/${sessionId}`);
  return data;
};

export const getHealth = async () => {
  const { data } = await axios.get(`${BACKEND_URL}/health`);
  return data;
};

export default api;