'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Plus, Trash2, X, Check, Power, PowerOff } from 'lucide-react';
import { alertApi } from '@/lib/api';
import { cn, formatRelative, formatNumber } from '@/lib/utils';
import type { Alert, AlertOperator, AggregationType } from '@/types';

const OPERATORS: { value: AlertOperator; label: string }[] = [
  { value: 'gt', label: 'greater than' },
  { value: 'gte', label: 'greater than or equal' },
  { value: 'lt', label: 'less than' },
  { value: 'lte', label: 'less than or equal' },
  { value: 'eq', label: 'equal to' },
  { value: 'neq', label: 'not equal to' },
];

export default function AlertsPage() {
  const qc = useQueryClient();
  const [editor, setEditor] = useState<{ open: boolean; alert?: Alert }>({ open: false });

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: alertApi.list,
  });

  const toggleEnabled = useMutation({
    mutationFn: ({ id, is_enabled }: { id: string; is_enabled: boolean }) =>
      alertApi.update(id, { is_enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  });

  const deleteAlert = useMutation({
    mutationFn: (id: string) => alertApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  });

  return (
    <div className="max-w-7xl mx-auto px-8 py-10">
      <div className="flex items-end justify-between mb-10">
        <div>
          <div className="text-xs uppercase tracking-widest text-ink-500 mb-2">Monitoring</div>
          <h1 className="font-display text-4xl font-medium tracking-tight">Alerts</h1>
        </div>
        <button onClick={() => setEditor({ open: true })} className="btn-primary">
          <Plus className="w-4 h-4" /> New alert
        </button>
      </div>

      <div className="divider-rule mb-8" />

      {isLoading ? (
        <div className="text-sm text-ink-400">Loading…</div>
      ) : alerts.length === 0 ? (
        <div className="card p-12 text-center">
          <AlertTriangle className="w-10 h-10 text-ink-300 mx-auto mb-4" />
          <div className="font-display text-2xl font-medium mb-2">No alerts configured</div>
          <div className="text-ink-500 text-sm mb-6 max-w-md mx-auto">
            Get notified when your metrics cross a threshold — via email, in-app, or webhook.
          </div>
          <button onClick={() => setEditor({ open: true })} className="btn-primary">
            <Plus className="w-4 h-4" /> Create alert
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className="card p-5 flex items-center justify-between hover:shadow-card-hover transition-all animate-fade-in"
            >
              <div className="flex items-start gap-4 flex-1 min-w-0">
                <div
                  className={cn(
                    'w-9 h-9 rounded flex items-center justify-center flex-shrink-0',
                    alert.status === 'triggered' ? 'bg-accent-50' : 'bg-ink-100',
                  )}
                >
                  <AlertTriangle
                    className={cn(
                      'w-4 h-4',
                      alert.status === 'triggered' ? 'text-accent' : 'text-ink-500',
                    )}
                  />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <div className="font-medium text-ink-900">{alert.name}</div>
                    {alert.status === 'triggered' && (
                      <span className="text-[10px] uppercase tracking-wider bg-accent-50 text-accent-700 px-1.5 py-0.5 rounded font-medium">
                        Triggered
                      </span>
                    )}
                    {!alert.is_enabled && (
                      <span className="text-[10px] uppercase tracking-wider bg-ink-100 text-ink-500 px-1.5 py-0.5 rounded">
                        Disabled
                      </span>
                    )}
                  </div>
                  {alert.description && (
                    <div className="text-sm text-ink-500 mb-2 line-clamp-1">
                      {alert.description}
                    </div>
                  )}
                  <div className="flex items-center gap-3 text-xs text-ink-500 tabular">
                    <span>
                      <strong className="text-ink-700">{alert.query_config.aggregation}</strong>
                      {alert.query_config.event_name && (
                        <> of <strong className="text-ink-700">{alert.query_config.event_name}</strong></>
                      )}
                      {' '}
                      <strong className="text-ink-700">
                        {OPERATORS.find((o) => o.value === alert.operator)?.label}
                      </strong>
                      {' '}
                      <strong className="text-ink-700">{formatNumber(alert.threshold)}</strong>
                    </span>
                    {alert.last_value !== null && (
                      <span>· Current: <strong className="text-ink-700">{formatNumber(alert.last_value)}</strong></span>
                    )}
                    {alert.last_triggered_at && (
                      <span>· Triggered {formatRelative(alert.last_triggered_at)}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1 ml-4">
                <button
                  onClick={() =>
                    toggleEnabled.mutate({ id: alert.id, is_enabled: !alert.is_enabled })
                  }
                  className="btn-ghost"
                  title={alert.is_enabled ? 'Disable alert' : 'Enable alert'}
                >
                  {alert.is_enabled ? (
                    <Power className="w-4 h-4 text-ink-700" />
                  ) : (
                    <PowerOff className="w-4 h-4 text-ink-400" />
                  )}
                </button>
                <button
                  onClick={() => setEditor({ open: true, alert })}
                  className="btn-ghost text-xs"
                >
                  Edit
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Delete alert "${alert.name}"?`)) {
                      deleteAlert.mutate(alert.id);
                    }
                  }}
                  className="btn-ghost"
                >
                  <Trash2 className="w-3.5 h-3.5 text-accent-700" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editor.open && (
        <AlertEditor
          alert={editor.alert}
          onClose={() => setEditor({ open: false })}
        />
      )}
    </div>
  );
}

function AlertEditor({ alert, onClose }: { alert?: Alert; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState(alert?.name || '');
  const [description, setDescription] = useState(alert?.description || '');
  const [eventName, setEventName] = useState(alert?.query_config.event_name || '');
  const [aggregation, setAggregation] = useState<AggregationType>(
    alert?.query_config.aggregation || 'count',
  );
  const [operator, setOperator] = useState<AlertOperator>(alert?.operator || 'gt');
  const [threshold, setThreshold] = useState(alert?.threshold?.toString() || '100');
  const [relative, setRelative] = useState(alert?.query_config.time_range?.relative || '5m');
  const [channels, setChannels] = useState<string[]>(alert?.channels || ['in_app']);
  const [emailRecipients, setEmailRecipients] = useState(
    (alert?.channel_config?.email_recipients as string[])?.join(', ') || '',
  );
  const [webhookUrl, setWebhookUrl] = useState(
    (alert?.channel_config?.webhook_url as string) || '',
  );

  const save = useMutation({
    mutationFn: () => {
      const payload: any = {
        name,
        description,
        query_config: {
          event_name: eventName || undefined,
          aggregation,
          filters: [],
          group_by: [],
          time_range: { relative },
          limit: 1000,
        },
        operator,
        threshold: parseFloat(threshold),
        check_interval_seconds: 60,
        cooldown_seconds: 300,
        channels,
        channel_config: {
          email_recipients: emailRecipients
            .split(',')
            .map((e) => e.trim())
            .filter(Boolean),
          webhook_url: webhookUrl || undefined,
        },
        is_enabled: alert?.is_enabled ?? true,
      };
      return alert ? alertApi.update(alert.id, payload) : alertApi.create(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] });
      onClose();
    },
  });

  function toggleChannel(ch: string) {
    setChannels((prev) =>
      prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch],
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in">
      <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-ink-200 flex items-center justify-between sticky top-0 bg-white">
          <div className="font-display text-xl font-medium">
            {alert ? 'Edit alert' : 'New alert'}
          </div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-ink-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} className="input-base" placeholder="High signup volume" />
          </Field>

          <Field label="Description (optional)">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="input-base resize-none"
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Event name (optional)">
              <input
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
                placeholder="signup"
                className="input-base"
              />
            </Field>
            <Field label="Aggregation">
              <select
                value={aggregation}
                onChange={(e) => setAggregation(e.target.value as AggregationType)}
                className="input-base"
              >
                <option value="count">count</option>
                <option value="sum">sum</option>
                <option value="avg">avg</option>
                <option value="min">min</option>
                <option value="max">max</option>
                <option value="distinct_count">distinct count</option>
              </select>
            </Field>
          </div>

          <Field label="Trigger when value is">
            <div className="grid grid-cols-2 gap-2">
              <select
                value={operator}
                onChange={(e) => setOperator(e.target.value as AlertOperator)}
                className="input-base"
              >
                {OPERATORS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="input-base"
              />
            </div>
          </Field>

          <Field label="Evaluate over">
            <select value={relative} onChange={(e) => setRelative(e.target.value)} className="input-base">
              <option value="5m">Last 5 minutes</option>
              <option value="15m">Last 15 minutes</option>
              <option value="1h">Last hour</option>
              <option value="24h">Last 24 hours</option>
            </select>
          </Field>

          <Field label="Notification channels">
            <div className="space-y-2">
              {[
                { val: 'in_app', label: 'In-app notification' },
                { val: 'email', label: 'Email' },
                { val: 'webhook', label: 'Webhook' },
              ].map((c) => (
                <label
                  key={c.val}
                  className={cn(
                    'flex items-center gap-3 p-3 border rounded cursor-pointer transition-all',
                    channels.includes(c.val)
                      ? 'border-ink-900 bg-ink-50'
                      : 'border-ink-200 hover:border-ink-400',
                  )}
                >
                  <div
                    className={cn(
                      'w-4 h-4 rounded border flex items-center justify-center transition-all',
                      channels.includes(c.val)
                        ? 'bg-ink-900 border-ink-900'
                        : 'border-ink-300',
                    )}
                  >
                    {channels.includes(c.val) && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <input
                    type="checkbox"
                    checked={channels.includes(c.val)}
                    onChange={() => toggleChannel(c.val)}
                    className="hidden"
                  />
                  <span className="text-sm">{c.label}</span>
                </label>
              ))}
            </div>
          </Field>

          {channels.includes('email') && (
            <Field label="Email recipients (comma-separated)">
              <input
                value={emailRecipients}
                onChange={(e) => setEmailRecipients(e.target.value)}
                placeholder="alice@acme.com, bob@acme.com"
                className="input-base"
              />
            </Field>
          )}

          {channels.includes('webhook') && (
            <Field label="Webhook URL">
              <input
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://hooks.slack.com/..."
                className="input-base"
              />
            </Field>
          )}
        </div>

        <div className="px-6 py-4 border-t border-ink-200 flex justify-end gap-2 sticky bottom-0 bg-white">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending || !name || channels.length === 0}
            className="btn-primary"
          >
            {save.isPending ? 'Saving…' : alert ? 'Save changes' : 'Create alert'}
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
