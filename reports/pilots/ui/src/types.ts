// Shapes of the Reports API v1 (reports/api/openapi/v1/openapi.yaml) used by the UI.

export interface Measure { key: string; title: string; formula: string }

export interface ReportDefinition {
  reportId: string;
  name: string;
  question: string;
  contour: 'ANALYTICAL' | 'OPERATIONAL';
  sources: string[];
  version: number;
  slices: string[];
  measures: Measure[];
}

export interface Freshness {
  source: string;
  stream: string;
  dataAsOf: string | null;
  lagSeconds: number | null;
  thresholdSeconds: number;
  state: 'UNKNOWN' | 'FRESH' | 'STALE';
}

export interface Column { key: string; title: string; type: 'dimension' | 'measure'; formula?: string }

export interface DimensionValue { id: string | null; label: string }

export type Cell = DimensionValue | number | string | null | Record<string, unknown> | unknown[];

export interface ReportResult {
  reportId: string;
  columns: Column[];
  rows: Record<string, Cell>[];
  totals: Record<string, Cell>;
  notes: string[];
  freshness: Freshness[];
  comparison: { periodFrom: string; periodTo: string; totals?: Record<string, Cell>; delta: Record<string, number> | null } | null;
}

export interface QueryParams {
  periodFrom: string;
  periodTo: string;
  projectIds?: string[];
  iterationIds?: string[];
  employeeIds?: string[];
}

export interface DimensionOption { id: string; label: string }

export interface Batch {
  batchId: string; source: string; status: 'EXTRACTING' | 'LOADED' | 'REJECTED';
  startedAt: string; finishedAt: string | null; rows: number | null; error: string | null;
}

export interface Reconciliation {
  reconciliationId: string; source: string; entity: string; sourceCount: number; dwhCount: number;
  missing: number; extra: number; mode: 'SOURCE' | 'LOCAL'; result: 'MATCH' | 'DRIFT'; checkedAt: string;
}

export interface LoadRequest { source: string; requestedAt: string; reason: string; status: 'PENDING' | 'COMPLETED' }

export interface ReportQuery { params: QueryParams; slice: string[]; compareWithPrevious?: boolean }

export interface SavedView { viewId: string; reportId: string; name: string; query: ReportQuery; createdAt: string }

export type ExportStatus = 'CREATED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'DELIVERED' | 'FAILED' | 'EXPIRED';

export interface ExportJob {
  exportId: string;
  reportId: string;
  format: 'csv' | 'xlsx';
  status: ExportStatus;
  createdAt: string;
  expiresAt: string | null;
  rowCount: number | null;
  error: string | null;
  query?: ReportQuery;
}

export interface Subscription {
  subscriptionId: string;
  reportId: string;
  query: ReportQuery;
  schedule: string;
  format: 'csv' | 'xlsx';
  recipients: string[];
  validUntil?: string | null;
  status: 'ACTIVE' | 'PAUSED' | 'COMPLETED';
  version: string;
  nextRunAt: string | null;
}

export interface Delivery { runAt?: string; delivered?: string[]; skipped?: { recipient: string; reason?: string }[]; [key: string]: unknown }

export interface Notification {
  notificationId: string;
  kind: string;
  exportId: string | null;
  snapshotId: string | null;
  createdAt: string;
  readAt: string | null;
}

export interface AuditEvent {
  auditId: number;
  actor: string;
  action: string;
  reportId: string | null;
  resourceId: string | null;
  queryHash: string | null;
  result: string;
  at: string;
  correlationId: string;
}

export interface Page<T> { items: T[]; total?: number }
