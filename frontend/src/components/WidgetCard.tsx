'use client';

import { useQuery } from '@tanstack/react-query';
import { Pencil, Trash2, MoreVertical } from 'lucide-react';
import { useState } from 'react';
import { dashboardApi } from '@/lib/api';
import type { Widget } from '@/types';
import { ChartRenderer } from './ChartRenderer';
import { cn } from '@/lib/utils';

interface WidgetCardProps {
  widget: Widget;
  refreshInterval?: number;
  onEdit?: () => void;
  onDelete?: () => void;
  canEdit?: boolean;
}

export function WidgetCard({
  widget,
  refreshInterval,
  onEdit,
  onDelete,
  canEdit = true,
}: WidgetCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['widget-data', widget.id],
    queryFn: () => dashboardApi.getWidgetData(widget.id),
    refetchInterval: refreshInterval && refreshInterval > 0 ? refreshInterval * 1000 : false,
  });

  const span = widget.layout?.w || 6;
  const tall = (widget.layout?.h || 4) >= 3;

  return (
    <div
      className={cn(
        'card p-4 flex flex-col animate-fade-in group',
        `col-span-12 md:col-span-${Math.min(span, 12)}`,
        tall ? 'min-h-[320px]' : 'min-h-[160px]',
      )}
      style={{ gridColumn: `span ${Math.min(span, 12)} / span ${Math.min(span, 12)}` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-ink-900 truncate">{widget.title}</div>
          <div className="text-[11px] text-ink-400 uppercase tracking-wider mt-0.5">
            {widget.chart_type}
          </div>
        </div>

        {canEdit && (
          <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-ink-100 transition-all"
            >
              <MoreVertical className="w-4 h-4 text-ink-500" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 card p-1 z-10 min-w-[140px]">
                {onEdit && (
                  <button
                    onClick={() => {
                      onEdit();
                      setMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-ink-700 hover:bg-ink-100 rounded transition-all"
                  >
                    <Pencil className="w-3.5 h-3.5" /> Edit
                  </button>
                )}
                {onDelete && (
                  <button
                    onClick={() => {
                      onDelete();
                      setMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-accent-700 hover:bg-accent-50 rounded transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-sm text-ink-400">
            Loading…
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-sm text-accent-700">
            Failed to load
          </div>
        ) : data ? (
          <ChartRenderer
            type={widget.chart_type}
            data={data}
            height={tall ? 240 : 100}
          />
        ) : null}
      </div>
    </div>
  );
}
