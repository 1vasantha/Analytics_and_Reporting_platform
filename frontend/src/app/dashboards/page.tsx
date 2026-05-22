'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, LayoutDashboard, Globe, Lock } from 'lucide-react';
import { dashboardApi } from '@/lib/api';
import { formatRelative } from '@/lib/utils';

export default function DashboardsPage() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const { data: dashboards = [], isLoading } = useQuery({
    queryKey: ['dashboards'],
    queryFn: dashboardApi.list,
  });

  const create = useMutation({
    mutationFn: () => dashboardApi.create({ name, description }),
    onSuccess: (dash) => {
      qc.invalidateQueries({ queryKey: ['dashboards'] });
      setShowNew(false);
      setName('');
      setDescription('');
      // Navigate to the new dashboard
      window.location.href = `/dashboards/${dash.id}`;
    },
  });

  return (
    <div className="max-w-7xl mx-auto px-8 py-10">
      <div className="flex items-end justify-between mb-10">
        <div>
          <div className="text-xs uppercase tracking-widest text-ink-500 mb-2">
            Workspace
          </div>
          <h1 className="font-display text-4xl font-medium tracking-tight">
            Dashboards
          </h1>
        </div>
        <button onClick={() => setShowNew(true)} className="btn-primary">
          <Plus className="w-4 h-4" />
          New dashboard
        </button>
      </div>

      <div className="divider-rule mb-8" />

      {isLoading ? (
        <div className="text-sm text-ink-400">Loading…</div>
      ) : dashboards.length === 0 ? (
        <div className="card p-12 text-center">
          <LayoutDashboard className="w-10 h-10 text-ink-300 mx-auto mb-4" />
          <div className="font-display text-2xl font-medium mb-2">
            Build your first dashboard
          </div>
          <div className="text-ink-500 text-sm mb-6 max-w-md mx-auto">
            Dashboards are collections of widgets that visualize your event data —
            counts, sums, trends, and more.
          </div>
          <button onClick={() => setShowNew(true)} className="btn-primary">
            <Plus className="w-4 h-4" /> Create dashboard
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {dashboards.map((d) => (
            <Link
              key={d.id}
              href={`/dashboards/${d.id}`}
              className="card p-5 hover:shadow-card-hover transition-all group block animate-fade-in"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-9 h-9 rounded bg-ink-100 flex items-center justify-center group-hover:bg-accent-50 transition-all">
                  <LayoutDashboard className="w-4 h-4 text-ink-700 group-hover:text-accent" />
                </div>
                {d.is_public ? (
                  <Globe className="w-3.5 h-3.5 text-ink-400" />
                ) : (
                  <Lock className="w-3.5 h-3.5 text-ink-400" />
                )}
              </div>
              <div className="font-display text-lg font-medium mb-1 tracking-tight">
                {d.name}
              </div>
              {d.description && (
                <div className="text-sm text-ink-500 line-clamp-2 mb-3">
                  {d.description}
                </div>
              )}
              <div className="text-xs text-ink-400 mt-auto">
                Updated {formatRelative(d.updated_at)}
              </div>
            </Link>
          ))}
        </div>
      )}

      {showNew && (
        <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in">
          <div className="card w-full max-w-md p-6">
            <div className="font-display text-2xl font-medium mb-1">
              New dashboard
            </div>
            <div className="text-sm text-ink-500 mb-6">
              Give your dashboard a name. You can add widgets next.
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (name.trim()) create.mutate();
              }}
              className="space-y-4"
            >
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
                  Name
                </label>
                <input
                  autoFocus
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Q4 Performance"
                  className="input-base"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
                  Description (optional)
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  className="input-base resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNew(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={create.isPending}
                  className="btn-primary"
                >
                  {create.isPending ? 'Creating…' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
