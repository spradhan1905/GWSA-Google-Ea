/**
 * GWSA GeoAnalytics — API Service
 * Axios base instance + all backend API calls.
 * Attaches a Microsoft Entra Bearer token on every request (when auth is configured).
 */
import axios from 'axios';
import { getApiAccessToken } from '../auth/msalInstance';
import { authConfigured } from '../auth/msalConfig';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
// If API_BASE_URL is empty, requests go to same-origin (/api/*).
// If API_BASE_URL is set (e.g. https://backend.example.com), we call `${API_BASE_URL}/api/*`.
const axiosBaseURL = `${API_BASE_URL}/api`.replace(/\/+$/, '/api');

const api = axios.create({
  baseURL: axiosBaseURL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: authConfigured,
});

// Request interceptor — attach MSAL access token if auth is configured
api.interceptors.request.use(async (config) => {
  if (!authConfigured) return config;
  const token = await getApiAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401 (expired token) and 429 (rate limit)
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status;
    if (status === 401) {
      console.warn('[API] 401 Unauthorized — token may be missing or expired');
    } else if (status === 429) {
      console.warn('[API] Rate limited — slow down');
    }
    return Promise.reject(err);
  }
);

export const fetchLocations = () => api.get('/locations');

/** thisMonth: when true, backend uses TotalCoreTableFinal daily revenue for the given start/end (This Month or Custom range). */
export const fetchFinancials = (storeId, start, end, { thisMonth = false } = {}) =>
  api.get(`/financials/${encodeURIComponent(storeId)}`, {
    params: { start, end, ...(thisMonth ? { this_month: true } : {}) },
  });

export const fetchDoorCount = (storeId, start, end) =>
  api.get(`/door-count/${encodeURIComponent(storeId)}`, { params: { start, end } });

export const fetchTrends = (storeId, months = 12) =>
  api.get(`/trends/${encodeURIComponent(storeId)}`, { params: { months } });

export const sendChatMessage = (message, storeContext, history) =>
  api.post('/chat', { message, store_context: storeContext, conversation_history: history });

export const checkHealth = () => api.get('/health');

export default api;
