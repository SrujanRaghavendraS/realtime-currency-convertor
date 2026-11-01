// Thin client for the FX Rate Monitor backend. Field names follow API_CONTRACT.md.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status; // undefined => network failure / backend unreachable
  }
}

async function request(path, { method = 'GET', body, timeoutMs = 10000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    throw new ApiError(
      err.name === 'AbortError' ? 'Backend did not respond in time' : 'Backend unreachable',
      undefined
    );
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`;
    throw new ApiError(detail, res.status);
  }
  return data;
}

export const getRates = (plan) => request(`/api/rates?plan=${encodeURIComponent(plan)}`);
export const getMetrics = () => request('/api/metrics');
export const getHealth = () => request('/health');
export const getDemoStatus = () => request('/api/demo/status');
export const getHistory = (pair) => request(`/api/history?pair=${encodeURIComponent(pair)}`);

export const startDemo = (plan, failureType) =>
  request(`/api/demo/${plan}/start`, {
    method: 'POST',
    body: plan === 'free' && failureType ? { failure_type: failureType } : undefined,
  });

export const stopDemo = (plan) => request(`/api/demo/${plan}/stop`, { method: 'POST' });
