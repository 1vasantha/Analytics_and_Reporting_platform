'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Plus, Settings, Trash2, RefreshCw } from 'lucide-react';
import { dashboardApi } from '@/lib/api';
import { WidgetCard } from '@/components/WidgetCard';
import { WidgetEditor } from '@/components/WidgetEditor';
import type { Widget } from '@/types';
import { formatRelative } from '@/lib/utils';

export default function DashboardDetailPage() {
  const params = useParams();
  const router = useRouter();
  const qc = useQueryClient();
  const id = params?.id as string;

  const [editor, setEditor] = useState<{ open: boolean; widget?: Widget }>({
    open: false,
  });
  const [showSettings, setShowSettings] = useState(false);

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['dashboard', id],
    queryFn: () => dashboardApi.get(id),
    enabled: !!id,
  });

  const deleteWidget = useMutation({
    mutationFn: (widgetId: string) => dashboardApi.deleteWidget(widgetId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboard', id] }),
  });

  const deleteDashboard = useMutation({
    mutationFn: () => dashboardApi.delete(id),
    onSuccess: () => router.push('/dashboards'),
  });

  function refreshAll() {
    qc.invalidateQueries({ queryKey: ['widget-data'] });
  }

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-8 py-10">
        <div className="text-sm text-ink-400">Loading dashboard…</div>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="max-w-7xl mx-auto px-8 py-10">
        <div className="text-sm text-accent-700">Dashboard not found</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-8 py-10">
      <button
        onClick={() => router.push('/dashboards')}
        className="text-sm text-ink-500 hover:text-ink-900 flex items-center gap-1 mb-4"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> All dashboards
      </button>

      <div className="flex items-start justify-between mb-2">
        <div>
          <h1 className="font-display text-4xl font-medium tracking-tight">
            {dashboard.name}
          </h1>
          {dashboard.description && (
            <div className="text-ink-500 mt-2 max-w-2xl">{dashboard.description}</div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={refreshAll} className="btn-ghost" title="Refresh data">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={() => setShowSettings(true)} className="btn-ghost">
            <Settings className="w-4 h-4" />
          </button>
          <button
            onClick={() => setEditor({ open: true })}
            className="btn-primary"
          >
            <Plus className="w-4 h-4" /> Add widget
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-ink-400 mb-8">
        <span>{dashboard.widgets.length} widgets</span>
        <span>·</span>
        <span>Updated {formatRelative(dashboard.updated_at)}</span>
        {dashboard.refresh_interval > 0 && (
          <>
            <span>·</span>
            <span>Auto-refresh every {dashboard.refresh_interval}s</span>
          </>
        )}
      </div>

      <div className="divider-rule mb-6" />

      {dashboard.widgets.length === 0 ? (
        <div className="card p-16 text-center">
          <div className="font-display text-2xl font-medium mb-2">
            No widgets yet
          </div>
          <div className="text-sm text-ink-500 mb-6">
            Add your first chart to bring this dashboard to life.
          </div>
          <button onClick={() => setEditor({ open: true })} className="btn-primary">
            <Plus className="w-4 h-4" /> Add widget
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-4 auto-rows-min">
          {dashboard.widgets.map((widget) => (
            <WidgetCard
              key={widget.id}
              widget={widget}
              refreshInterval={dashboard.refresh_interval}
              onEdit={() => setEditor({ open: true, widget })}
              onDelete={() => {
                if (confirm(`Delete widget "${widget.title}"?`)) {
                  deleteWidget.mutate(widget.id);
                }
              }}
            />
          ))}
        </div>
      )}

      {editor.open && (
        <WidgetEditor
          dashboardId={id}
          initial={editor.widget}
          onClose={() => setEditor({ open: false })}
          onSaved={() => setEditor({ open: false })}
        />
      )}

      {showSettings && (
        <DashboardSettingsModal
          dashboard={dashboard}
          onClose={() => setShowSettings(false)}
          onDelete={() => {
            if (confirm(`Delete dashboard "${dashboard.name}"? This cannot be undone.`)) {
              deleteDashboard.mutate();
            }
          }}
        />
      )}
    </div>
  );
}

function DashboardSettingsModal({
  dashboard,
  onClose,
  onDelete,
}: {
  dashboard: any;
  onClose: () => void;
  onDelete: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(dashboard.name);
  const [description, setDescription] = useState(dashboard.description || '');
  const [refreshInterval, setRefreshInterval] = useState(dashboard.refresh_interval);
  const [isPublic, setIsPublic] = useState(dashboard.is_public);

  const save = useMutation({
    mutationFn: () =>
      dashboardApi.update(dashboard.id, {
        name,
        description,
        refresh_interval: refreshInterval,
        is_public: isPublic,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dashboard', dashboard.id] });
      qc.invalidateQueries({ queryKey: ['dashboards'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-6">
      <div className="card w-full max-w-lg p-6">
        <div className="font-display text-2xl font-medium mb-6">
          Dashboard settings
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
              Name
            </label>
            <input value={name} onChange={(e) => setName(e.target.value)} className="input-base" />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="input-base resize-none"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
              Auto-refresh interval (seconds)
            </label>
            <input
              type="number"
              min={0}
              max={3600}
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(parseInt(e.target.value) || 0)}
              className="input-base"
            />
            <div className="text-xs text-ink-400">0 = disabled (still updates via WebSocket)</div>
          </div>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
            />
            <div>
              <div className="text-sm font-medium">Public sharing</div>
              <div className="text-xs text-ink-500">
                Generate a shareable link that anyone can view
              </div>
            </div>
          </label>

          {dashboard.share_token && isPublic && (
            <div className="bg-ink-50 rounded p-3 text-xs font-mono text-ink-700 break-all">
              {typeof window !== 'undefined' && window.location.origin}/share/{dashboard.share_token}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between mt-8">
          <button onClick={onDelete} className="text-sm text-accent-700 hover:text-accent-600 flex items-center gap-1.5">
            <Trash2 className="w-3.5 h-3.5" /> Delete dashboard
          </button>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn-secondary">Cancel</button>
            <button
              onClick={() => save.mutate()}
              disabled={save.isPending}
              className="btn-primary"
            >
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
