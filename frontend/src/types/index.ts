// Mirrors backend Pydantic schemas. Keep in sync with `backend/app/schemas/`.

export type UserRole = 'owner' | 'admin' | 'analyst' | 'viewer';
export type ChartType = 'line' | 'bar' | 'pie' | 'kpi' | 'area' | 'table';
export type AggregationType = 'count' | 'sum' | 'avg' | 'min' | 'max' | 'distinct_count';
export type TimeGranularity = 'minute' | 'hour' | 'day' | 'week' | 'month';
export type AlertOperator = 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'neq';
export type AlertStatus = 'ok' | 'triggered' | 'silenced';
export type NotificationChannel = 'email' | 'in_app' | 'webhook';
export type ReportFrequency = 'daily' | 'weekly' | 'monthly';
export type FilterOperator =
  | 'eq' | 'neq' | 'in' | 'not_in' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  organization_id: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  tokens: TokenResponse;
  user: User;
  organization: Organization;
}

// ----- Metric queries -----

export interface FilterCondition {
  field: string;
  operator: FilterOperator;
  value: unknown;
}

export interface TimeRange {
  start?: string;
  end?: string;
  relative?: string;
}

export interface MetricQuery {
  event_name?: string;
  source?: string;
  aggregation: AggregationType;
  value_field?: string;
  filters?: FilterCondition[];
  group_by?: string[];
  granularity?: TimeGranularity;
  time_range: TimeRange;
  limit?: number;
}

export interface TimeSeriesPoint {
  timestamp: string;
  value: number;
  group: string | null;
}

export interface MetricQueryResult {
  aggregation: AggregationType;
  granularity: TimeGranularity | null;
  points: TimeSeriesPoint[];
  total: number;
  metadata: Record<string, unknown>;
}

// ----- Dashboards -----

export interface WidgetLayout {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Widget {
  id: string;
  dashboard_id: string;
  title: string;
  chart_type: ChartType;
  query_config: MetricQuery;
  layout: WidgetLayout;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface Dashboard {
  id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  refresh_interval: number;
  share_token: string | null;
  widgets: Widget[];
  created_at: string;
  updated_at: string;
}

export interface DashboardSummary {
  id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  refresh_interval: number;
  created_at: string;
  updated_at: string;
}

// ----- Alerts -----

export interface Alert {
  id: string;
  name: string;
  description: string | null;
  query_config: MetricQuery;
  operator: AlertOperator;
  threshold: number;
  check_interval_seconds: number;
  cooldown_seconds: number;
  channels: string[];
  channel_config: Record<string, unknown>;
  status: AlertStatus;
  is_enabled: boolean;
  last_checked_at: string | null;
  last_triggered_at: string | null;
  last_value: number | null;
  created_at: string;
  updated_at: string;
}

export interface Notification {
  id: string;
  alert_id: string | null;
  title: string;
  message: string;
  severity: string;
  is_read: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
}

// ----- API Keys -----

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked: boolean;
}

export interface ApiKeyCreated {
  id: string;
  name: string;
  key: string; // full key — shown once
  prefix: string;
}

// ----- Ingestion -----

export interface IngestionJob {
  id: string;
  filename: string;
  status: string;
  total_rows: number;
  processed_rows: number;
  failed_rows: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

// ----- Reports -----

export interface ScheduledReport {
  id: string;
  name: string;
  dashboard_id: string;
  frequency: ReportFrequency;
  recipients: string[];
  is_enabled: boolean;
  last_sent_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}
