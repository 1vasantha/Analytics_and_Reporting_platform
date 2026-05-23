import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type {
  Alert,
  ApiKey,
  ApiKeyCreated,
  AuthResponse,
  Dashboard,
  DashboardSummary,
  IngestionJob,
  MetricQuery,
  MetricQueryResult,
  Notification,
  ScheduledReport,
  TokenResponse,
  User,
  Widget,
} from '@/types';

const API_BASE = typeof window === 'undefined' 
  ? process.env.API_URL || 'http://localhost:8000'  // server-side
  : '';  // browser — use relative URL, proxied by Next.js
  
const STORAGE_ACCESS = 'auth.access_token';
const STORAGE_REFRESH = 'auth.refresh_token';

export const tokenStorage = {
  getAccess(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(STORAGE_ACCESS);
  },
  getRefresh(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(STORAGE_REFRESH);
  },
  set(access: string, refresh: string) {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_ACCESS, access);
    localStorage.setItem(STORAGE_REFRESH, refresh);
  },
  clear() {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(STORAGE_ACCESS);
    localStorage.removeItem(STORAGE_REFRESH);
  },
};

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

// ----- Request interceptor: attach access token -----
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStorage.getAccess();
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ----- Response interceptor: handle 401 with refresh -----
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise;
  const refresh = tokenStorage.getRefresh();
  if (!refresh) throw new Error('No refresh token');

  refreshPromise = axios
    .post<TokenResponse>(`${API_BASE}/api/v1/auth/refresh`, {
      refresh_token: refresh,
    })
    .then((r) => {
      tokenStorage.set(r.data.access_token, r.data.refresh_token);
      return r.data.access_token;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

api.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes('/auth/')
    ) {
      original._retry = true;
      try {
        const newToken = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch {
        tokenStorage.clear();
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  },
);

// ===== Typed endpoint wrappers =====

export const authApi = {
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
  }) => api.post<AuthResponse>('/auth/register', data).then((r) => r.data),

  login: (data: { email: string; password: string }) =>
    api.post<AuthResponse>('/auth/login', data).then((r) => r.data),

  logout: () => {
    const refresh = tokenStorage.getRefresh();
    if (!refresh) return Promise.resolve();
    return api.post('/auth/logout', { refresh_token: refresh });
  },

  me: () => api.get<User>('/auth/me').then((r) => r.data),

  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
};

export const dashboardApi = {
  list: () => api.get<DashboardSummary[]>('/dashboards').then((r) => r.data),
  get: (id: string) => api.get<Dashboard>(`/dashboards/${id}`).then((r) => r.data),
  create: (data: { name: string; description?: string; refresh_interval?: number }) =>
    api.post<Dashboard>('/dashboards', data).then((r) => r.data),
  update: (id: string, data: Partial<{ name: string; description: string; is_public: boolean; refresh_interval: number }>) =>
    api.patch<Dashboard>(`/dashboards/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/dashboards/${id}`),

  addWidget: (
    dashboardId: string,
    data: { title: string; chart_type: string; query_config: MetricQuery; layout?: object; position?: number }
  ) => api.post<Widget>(`/dashboards/${dashboardId}/widgets`, data).then((r) => r.data),
  updateWidget: (id: string, data: Partial<Widget>) =>
    api.patch<Widget>(`/dashboards/widgets/${id}`, data).then((r) => r.data),
  deleteWidget: (id: string) => api.delete(`/dashboards/widgets/${id}`),

  runQuery: (query: MetricQuery) =>
    api.post<MetricQueryResult>('/dashboards/query', query).then((r) => r.data),
  getWidgetData: (id: string) =>
    api.get<MetricQueryResult>(`/dashboards/widgets/${id}/data`).then((r) => r.data),
};

export const ingestionApi = {
  listJobs: () => api.get<IngestionJob[]>('/ingest/jobs').then((r) => r.data),
  uploadCsv: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api
      .post<IngestionJob>('/ingest/csv', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  listApiKeys: () => api.get<ApiKey[]>('/ingest/api-keys').then((r) => r.data),
  createApiKey: (name: string) =>
    api.post<ApiKeyCreated>('/ingest/api-keys', { name }).then((r) => r.data),
  revokeApiKey: (id: string) => api.delete(`/ingest/api-keys/${id}`),
};

export const alertApi = {
  list: () => api.get<Alert[]>('/alerts').then((r) => r.data),
  get: (id: string) => api.get<Alert>(`/alerts/${id}`).then((r) => r.data),
  create: (data: Partial<Alert>) => api.post<Alert>('/alerts', data).then((r) => r.data),
  update: (id: string, data: Partial<Alert>) =>
    api.patch<Alert>(`/alerts/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/alerts/${id}`),
};

export const notificationApi = {
  list: (params?: { unread_only?: boolean; limit?: number }) =>
    api.get<Notification[]>('/notifications', { params }).then((r) => r.data),
  unreadCount: () =>
    api.get<{ unread: number }>('/notifications/unread-count').then((r) => r.data),
  markRead: (id: string) => api.post(`/notifications/${id}/read`),
  markAllRead: () => api.post('/notifications/read-all'),
};

export const reportApi = {
  list: () => api.get<ScheduledReport[]>('/reports').then((r) => r.data),
  create: (data: {
    name: string;
    dashboard_id: string;
    frequency: string;
    recipients: string[];
  }) => api.post<ScheduledReport>('/reports', data).then((r) => r.data),
  update: (id: string, data: Partial<ScheduledReport>) =>
    api.patch<ScheduledReport>(`/reports/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/reports/${id}`),
};
