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

export const clearSession = async (sessionId) => {
  const { data } = await api.delete(`/session/${sessionId}`);
  return data;
};

export const getHealth = async () => {
  const { data } = await axios.get(`${BACKEND_URL}/health`);
  return data;
};

export default api;