'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { dashboardApi } from '@/lib/api';
import type { AggregationType, ChartType, MetricQuery, TimeGranularity, Widget } from '@/types';
import { ChartRenderer } from './ChartRenderer';

interface WidgetEditorProps {
  dashboardId: string;
  initial?: Widget;
  onClose: () => void;
  onSaved: () => void;
}

const RELATIVE_OPTIONS = [
  { value: '1h', label: 'Last hour' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
];

const CHART_TYPES: ChartType[] = ['kpi', 'line', 'bar', 'area', 'pie', 'table'];
const AGGREGATIONS: AggregationType[] = ['count', 'sum', 'avg', 'min', 'max', 'distinct_count'];
const GRANULARITIES: (TimeGranularity | '')[] = ['', 'minute', 'hour', 'day', 'week', 'month'];

export function WidgetEditor({ dashboardId, initial, onClose, onSaved }: WidgetEditorProps) {
  const qc = useQueryClient();
  const [title, setTitle] = useState(initial?.title || 'New widget');
  const [chartType, setChartType] = useState<ChartType>(initial?.chart_type || 'line');
  const [eventName, setEventName] = useState(initial?.query_config.event_name || '');
  const [aggregation, setAggregation] = useState<AggregationType>(
    initial?.query_config.aggregation || 'count',
  );
  const [valueField, setValueField] = useState(initial?.query_config.value_field || 'value');
  const [granularity, setGranularity] = useState<TimeGranularity | ''>(
    initial?.query_config.granularity || (chartType === 'line' || chartType === 'area' || chartType === 'bar' ? 'day' : ''),
  );
  const [groupBy, setGroupBy] = useState<string>(
    (initial?.query_config.group_by || []).join(','),
  );
  const [relative, setRelative] = useState(
    initial?.query_config.time_range?.relative || '7d',
  );
  const [preview, setPreview] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const needsValueField = ['sum', 'avg', 'min', 'max'].includes(aggregation);

  function buildQuery(): MetricQuery {
    return {
      event_name: eventName || undefined,
      aggregation,
      value_field: needsValueField ? valueField : undefined,
      granularity: granularity || undefined,
      group_by: groupBy ? groupBy.split(',').map((s) => s.trim()).filter(Boolean) : [],
      filters: [],
      time_range: { relative },
      limit: 1000,
    };
  }

  const previewMutation = useMutation({
    mutationFn: () => dashboardApi.runQuery(buildQuery()),
    onSuccess: (data) => {
      setPreview(data);
      setError(null);
    },
    onError: (err: any) => {
      setError(err?.response?.data?.message || 'Query failed');
      setPreview(null);
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        title,
        chart_type: chartType,
        query_config: buildQuery(),
        layout: initial?.layout || { x: 0, y: 0, w: chartType === 'kpi' ? 3 : 6, h: chartType === 'kpi' ? 2 : 4 },
        position: initial?.position ?? 0,
      };

      if (initial) {
        return dashboardApi.updateWidget(initial.id, payload as any);
      }
      return dashboardApi.addWidget(dashboardId, payload as any);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dashboard', dashboardId] });
      onSaved();
    },
    onError: (err: any) => {
      setError(err?.response?.data?.message || 'Save failed');
    },
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-ink-200 flex items-center justify-between">
          <div className="font-display text-xl font-medium">
            {initial ? 'Edit widget' : 'New widget'}
          </div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-ink-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Form */}
          <div className="w-80 p-6 border-r border-ink-200 overflow-y-auto space-y-4">
            <Field label="Title">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="input-base"
              />
            </Field>

            <Field label="Chart type">
              <div className="grid grid-cols-3 gap-1.5">
                {CHART_TYPES.map((t) => (
                  <button
                    key={t}
                    onClick={() => setChartType(t)}
                    className={`px-2 py-1.5 text-xs rounded border transition-all capitalize ${
                      chartType === t
                        ? 'bg-ink-900 text-white border-ink-900'
                        : 'bg-white text-ink-700 border-ink-200 hover:border-ink-400'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Event name (optional)">
              <input
                placeholder="signup, purchase, click…"
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
                className="input-base"
              />
            </Field>

            <Field label="Aggregation">
              <select
                value={aggregation}
                onChange={(e) => setAggregation(e.target.value as AggregationType)}
                className="input-base"
              >
                {AGGREGATIONS.map((a) => (
                  <option key={a} value={a}>
                    {a.replace('_', ' ')}
                  </option>
                ))}
              </select>
            </Field>

            {needsValueField && (
              <Field label="Value field">
                <input
                  placeholder="value or properties.amount"
                  value={valueField}
                  onChange={(e) => setValueField(e.target.value)}
                  className="input-base"
                />
              </Field>
            )}

            <Field label="Time granularity">
              <select
                value={granularity}
                onChange={(e) => setGranularity(e.target.value as TimeGranularity)}
                className="input-base"
              >
                <option value="">— none (totals)</option>
                {GRANULARITIES.filter(Boolean).map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Group by (comma-separated)">
              <input
                placeholder="source, properties.country"
                value={groupBy}
                onChange={(e) => setGroupBy(e.target.value)}
                className="input-base"
              />
            </Field>

            <Field label="Time range">
              <select
                value={relative}
                onChange={(e) => setRelative(e.target.value)}
                className="input-base"
              >
                {RELATIVE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </Field>

            <button
              onClick={() => previewMutation.mutate()}
              disabled={previewMutation.isPending}
              className="btn-secondary w-full"
            >
              {previewMutation.isPending ? 'Running…' : 'Run preview'}
            </button>
          </div>

          {/* Preview */}
          <div className="flex-1 p-6 overflow-auto bg-ink-50/30">
            <div className="text-xs uppercase tracking-wider text-ink-500 mb-3">
              Preview
            </div>

            {error && (
              <div className="px-3 py-2 rounded bg-accent-50 text-accent-700 text-sm border border-accent-100 mb-3">
                {error}
              </div>
            )}

            <div className="card p-6 min-h-[300px]">
              <div className="text-sm font-medium mb-4">{title}</div>
              {preview ? (
                <ChartRenderer type={chartType} data={preview} height={280} />
              ) : (
                <div className="flex items-center justify-center h-[280px] text-sm text-ink-400">
                  Run a preview to see your chart
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-ink-200 flex items-center justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="btn-primary"
          >
            {saveMutation.isPending ? 'Saving…' : initial ? 'Save changes' : 'Add widget'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
        {label}
      </label>
      {children}
    </div>
  );
}
