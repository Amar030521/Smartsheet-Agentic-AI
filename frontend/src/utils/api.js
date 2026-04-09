import axios from 'axios';

// Backend URL: set REACT_APP_API_URL in Vercel environment variables
// e.g. https://your-backend.onrender.com
const BACKEND_URL = process.env.REACT_APP_API_URL || '';

const api = axios.create({
  baseURL: `${BACKEND_URL}/api/v1`,
  timeout: 300000, // 5 min for complex recursive queries
  headers: { 'Content-Type': 'application/json' }
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