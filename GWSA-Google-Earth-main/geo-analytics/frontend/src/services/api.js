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

/** Default axios timeout for quick API calls (not chat — chat overrides below). */
const DEFAULT_TIMEOUT_MS =
  Number(import.meta.env.VITE_API_TIMEOUT_MS) > 0
    ? Number(import.meta.env.VITE_API_TIMEOUT_MS)
    : 60000;

/** Chat runs DB work + LLM; allow longer wait than general API (was 60s and caused ECONNABORTED). */
const CHAT_TIMEOUT_MS =
  Number(import.meta.env.VITE_CHAT_TIMEOUT_MS) > 0
    ? Number(import.meta.env.VITE_CHAT_TIMEOUT_MS)
    : 300000;

const api = axios.create({
  baseURL: axiosBaseURL,
  timeout: DEFAULT_TIMEOUT_MS,
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

export const fetchDonations = (storeId, start, end) =>
  api.get(`/donations/${encodeURIComponent(storeId)}`, { params: { start, end } });

/** grain: 'day' (This Month / Custom) or 'month' (Rolling 3 months / YTD / 12 Months). Actual vs Budget Core revenue. */
export const fetchBudgetVsActual = (storeId, start, end, { grain = 'day' } = {}) =>
  api.get(`/budget-vs-actual/${encodeURIComponent(storeId)}`, {
    params: { start, end, grain },
  });

/** Pass { start, end } to align trends with the date picker; otherwise { months }. */
export const fetchTrends = (storeId, { months = 12, start, end } = {}) =>
  api.get(`/trends/${encodeURIComponent(storeId)}`, {
    params: start && end ? { start, end } : { months },
  });

export const fetchKeyMetrics = (storeId, { asOf } = {}) =>
  api.get(`/key-metrics/${encodeURIComponent(storeId)}`, {
    params: asOf ? { as_of: asOf } : {},
  });

export const sendChatMessage = (message, storeContext, history, sessionState = null) =>
  api.post(
    '/chat',
    {
      message,
      store_context: storeContext,
      conversation_history: history,
      ...(sessionState && typeof sessionState === 'object' ? { session_state: sessionState } : {}),
    },
    { timeout: CHAT_TIMEOUT_MS },
  );

/**
 * Streaming chat via Server-Sent Events (POST). Tokens arrive incrementally so the UI can
 * render the answer as it is generated instead of waiting for the whole response.
 *
 * Callbacks: onMeta(meta), onDelta(textChunk, fullText), onDone({ reply }), onError(err).
 * Returns a function that aborts the in-flight request.
 */
export const streamChatMessage = (
  message,
  storeContext,
  history,
  sessionState = null,
  { onMeta, onDelta, onDone, onError } = {},
) => {
  const controller = new AbortController();

  (async () => {
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (authConfigured) {
        const token = await getApiAccessToken();
        if (token) headers.Authorization = `Bearer ${token}`;
      }

      const resp = await fetch(`${axiosBaseURL}/chat/stream`, {
        method: 'POST',
        headers,
        credentials: authConfigured ? 'include' : 'same-origin',
        signal: controller.signal,
        body: JSON.stringify({
          message,
          store_context: storeContext,
          conversation_history: history,
          ...(sessionState && typeof sessionState === 'object' ? { session_state: sessionState } : {}),
        }),
      });

      if (!resp.ok || !resp.body) {
        let detail = '';
        try {
          const j = await resp.json();
          detail = j?.error || j?.reply || '';
        } catch { /* ignore */ }
        const err = new Error(detail || `Chat stream failed (${resp.status})`);
        err.status = resp.status;
        throw err;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';
      let finalReply = '';

      const handleEvent = (rawEvent) => {
        const lines = rawEvent.split('\n');
        let eventName = 'message';
        const dataLines = [];
        for (const line of lines) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
        }
        if (!dataLines.length) return;
        let payload;
        try {
          payload = JSON.parse(dataLines.join('\n'));
        } catch {
          return;
        }
        if (eventName === 'meta') {
          onMeta?.(payload);
        } else if (eventName === 'delta') {
          fullText += payload.text || '';
          onDelta?.(payload.text || '', fullText);
        } else if (eventName === 'done') {
          finalReply = payload.reply || fullText;
        } else if (eventName === 'error') {
          throw new Error(payload.error || 'AI service error');
        }
      };

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let sep;
        while ((sep = buffer.indexOf('\n\n')) !== -1) {
          const rawEvent = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          if (rawEvent.trim()) handleEvent(rawEvent);
        }
      }
      if (buffer.trim()) handleEvent(buffer);

      onDone?.({ reply: finalReply || fullText });
    } catch (err) {
      if (err.name === 'AbortError') return;
      onError?.(err);
    }
  })();

  return () => controller.abort();
};

export const checkHealth = () => api.get('/health');

/** Texas ACS tract layer (~7k polygons). Built via backend build script. */
const CENSUS_LAYER_TIMEOUT_MS = 180000;

export const fetchTexasTractIncomeMeta = () =>
  api.get('/census/texas-tract-income/meta', { timeout: 30000 });

export const fetchTexasTractIncomeLayer = () =>
  api.get('/census/texas-tract-income', { timeout: CENSUS_LAYER_TIMEOUT_MS });

export default api;
