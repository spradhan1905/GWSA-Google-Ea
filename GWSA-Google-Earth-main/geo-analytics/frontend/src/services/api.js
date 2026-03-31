/**
 * GWSA GeoAnalytics — API Service
 * Axios base instance + all backend API calls.
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
// If API_BASE_URL is empty, requests go to same-origin (/api/*).
// If API_BASE_URL is set (e.g. https://backend.example.com), we call `${API_BASE_URL}/api/*`.
const axiosBaseURL = `${API_BASE_URL}/api`.replace(/\/+$/, '/api');

const api = axios.create({
  baseURL: axiosBaseURL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Response interceptor for 429 rate limit handling
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 429) {
      console.warn('[API] Rate limited — slow down');
    }
    return Promise.reject(err);
  }
);

export const fetchLocations = () => api.get('/locations');

/** thisMonth: when true, backend reads JS_API.dbo.SalesFactFinal (This Month preset only). */
export const fetchFinancials = (storeId, start, end, { thisMonth = false } = {}) =>
  api.get(`/financials/${encodeURIComponent(storeId)}`, {
    params: { start, end, ...(thisMonth ? { this_month: true } : {}) },
  });

export const fetchDoorCount = (storeId, start, end) =>
  api.get(`/door-count/${encodeURIComponent(storeId)}`, { params: { start, end } });

export const fetchTrends = (storeId, months = 12) =>
  api.get(`/trends/${encodeURIComponent(storeId)}`, { params: { months } });

export const fetchDonorAddresses = (storeId) =>
  api.get(`/donor-addresses/${encodeURIComponent(storeId)}`);

export const sendChatMessage = (message, storeContext, history) =>
  api.post('/chat', { message, store_context: storeContext, conversation_history: history });

export const checkHealth = () => api.get('/health');

export default api;
