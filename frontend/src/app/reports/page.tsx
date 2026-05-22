'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Plus, Trash2, X, Mail } from 'lucide-react';
import { dashboardApi, reportApi } from '@/lib/api';
import { formatRelative } from '@/lib/utils';
import type { ReportFrequency, ScheduledReport } from '@/types';

export default function ReportsPage() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);

  const { data: reports = [], isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: reportApi.list,
  });

  const deleteReport = useMutation({
    mutationFn: (id: string) => reportApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] }),
  });

  return (
    <div className="max-w-7xl mx-auto px-8 py-10">
      <div className="flex items-end justify-between mb-10">
        <div>
          <div className="text-xs uppercase tracking-widest text-ink-500 mb-2">Delivery</div>
          <h1 className="font-display text-4xl font-medium tracking-tight">Reports</h1>
        </div>
        <button onClick={() => setShowNew(true)} className="btn-primary">
          <Plus className="w-4 h-4" /> New report
        </button>
      </div>

      <div className="divider-rule mb-8" />

      {isLoading ? (
        <div className="text-sm text-ink-400">Loading…</div>
      ) : reports.length === 0 ? (
        <div className="card p-12 text-center">
          <FileText className="w-10 h-10 text-ink-300 mx-auto mb-4" />
          <div className="font-display text-2xl font-medium mb-2">No scheduled reports</div>
          <div className="text-ink-500 text-sm mb-6 max-w-md mx-auto">
            Schedule dashboards to be emailed to your team daily, weekly, or monthly.
          </div>
          <button onClick={() => setShowNew(true)} className="btn-primary">
            <Plus className="w-4 h-4" /> Create report
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {reports.map((report) => (
            <div
              key={report.id}
              className="card p-5 flex items-center justify-between hover:shadow-card-hover transition-all animate-fade-in"
            >
              <div className="flex items-start gap-4 flex-1 min-w-0">
                <div className="w-9 h-9 rounded bg-ink-100 flex items-center justify-center">
                  <FileText className="w-4 h-4 text-ink-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-ink-900">{report.name}</div>
                  <div className="text-xs text-ink-500 mt-1 flex items-center gap-3">
                    <span className="capitalize">{report.frequency}</span>
                    <span>·</span>
                    <span className="flex items-center gap-1">
                      <Mail className="w-3 h-3" /> {report.recipients.length} recipient{report.recipients.length !== 1 && 's'}
                    </span>
                    {report.last_sent_at && (
                      <>
                        <span>·</span>
                        <span>Last sent {formatRelative(report.last_sent_at)}</span>
                      </>
                    )}
                    {report.next_run_at && (
                      <>
                        <span>·</span>
                        <span>Next: {new Date(report.next_run_at).toLocaleDateString()}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <button
                onClick={() => {
                  if (confirm(`Delete report "${report.name}"?`)) {
                    deleteReport.mutate(report.id);
                  }
                }}
                className="btn-ghost"
              >
                <Trash2 className="w-3.5 h-3.5 text-accent-700" />
              </button>
            </div>
          ))}
        </div>
      )}

      {showNew && <NewReportModal onClose={() => setShowNew(false)} />}
    </div>
  );
}

function NewReportModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [dashboardId, setDashboardId] = useState('');
  const [frequency, setFrequency] = useState<ReportFrequency>('weekly');
  const [recipients, setRecipients] = useState('');

  const { data: dashboards = [] } = useQuery({
    queryKey: ['dashboards'],
    queryFn: dashboardApi.list,
  });

  const create = useMutation({
    mutationFn: () =>
      reportApi.create({
        name,
        dashboard_id: dashboardId,
        frequency,
        recipients: recipients
          .split(',')
          .map((e) => e.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reports'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in">
      <div className="card w-full max-w-md">
        <div className="px-6 py-4 border-b border-ink-200 flex items-center justify-between">
          <div className="font-display text-xl font-medium">New scheduled report</div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-ink-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="p-6 space-y-4"
        >
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required className="input-base" />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">Dashboard</label>
            <select
              value={dashboardId}
              onChange={(e) => setDashboardId(e.target.value)}
              required
              className="input-base"
            >
              <option value="">Select…</option>
              {dashboards.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">Frequency</label>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value as ReportFrequency)}
              className="input-base"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
              Recipients (comma-separated)
            </label>
            <input
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              placeholder="alice@acme.com, bob@acme.com"
              required
              className="input-base"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={create.isPending} className="btn-primary">
              {create.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
