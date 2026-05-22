'use client';

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { ChartType, MetricQueryResult, TimeSeriesPoint } from '@/types';
import { formatCompact, formatNumber } from '@/lib/utils';

interface ChartProps {
  type: ChartType;
  data: MetricQueryResult;
  height?: number;
}

const CHART_COLORS = [
  '#e8602c',
  '#2d8f7a',
  '#d4a72c',
  '#5e7ce2',
  '#9d3415',
  '#7a766e',
  '#3d3b37',
  '#5a5751',
];

function formatTimestamp(ts: string, granularity: string | null): string {
  const d = new Date(ts);
  if (granularity === 'minute') return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (granularity === 'hour') return d.toLocaleTimeString([], { hour: '2-digit' });
  if (granularity === 'day') return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  if (granularity === 'week') return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  if (granularity === 'month') return d.toLocaleDateString([], { month: 'short' });
  return d.toLocaleDateString();
}

interface TooltipPayload {
  name?: string;
  value?: number;
  color?: string;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayload[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-ink-200 rounded shadow-lg px-3 py-2 text-xs">
      {label && <div className="font-medium text-ink-900 mb-1">{label}</div>}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 tabular">
          {p.color && (
            <div className="w-2 h-2 rounded-sm" style={{ background: p.color }} />
          )}
          <span className="text-ink-600">{p.name || 'Value'}:</span>
          <span className="font-medium text-ink-900">{formatNumber(p.value ?? 0)}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Pivot points into a structure suitable for multi-series charts.
 * Returns { rows: [{ts, group1: val, group2: val}], groups: [...] }.
 */
function pivotPoints(points: TimeSeriesPoint[], granularity: string | null) {
  const hasGroups = points.some((p) => p.group !== null);

  if (!hasGroups) {
    return {
      rows: points.map((p) => ({
        ts: formatTimestamp(p.timestamp, granularity),
        value: p.value,
      })),
      groups: ['value'],
    };
  }

  const groupSet = new Set<string>();
  const tsMap = new Map<string, Record<string, number | string>>();

  for (const p of points) {
    const ts = formatTimestamp(p.timestamp, granularity);
    const g = p.group || 'unknown';
    groupSet.add(g);
    if (!tsMap.has(ts)) tsMap.set(ts, { ts });
    tsMap.get(ts)![g] = p.value;
  }

  return {
    rows: Array.from(tsMap.values()),
    groups: Array.from(groupSet),
  };
}

export function ChartRenderer({ type, data, height = 240 }: ChartProps) {
  if (type === 'kpi') {
    return <KPICard data={data} />;
  }

  if (data.points.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-ink-400" style={{ height }}>
        No data
      </div>
    );
  }

  if (type === 'pie') {
    const pieData = data.points.map((p) => ({
      name: p.group || 'Total',
      value: p.value,
    }));
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={pieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius="75%"
            innerRadius="45%"
            paddingAngle={2}
          >
            {pieData.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
          <Legend
            iconType="square"
            iconSize={8}
            wrapperStyle={{ fontSize: '11px', fontFamily: 'Geist' }}
          />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  const { rows, groups } = pivotPoints(data.points, data.granularity);

  if (type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="ts" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={formatCompact} tickLine={false} axisLine={false} />
          <Tooltip content={<ChartTooltip />} />
          {groups.length > 1 && (
            <Legend iconType="line" iconSize={12} wrapperStyle={{ fontSize: '11px' }} />
          )}
          {groups.map((g, i) => (
            <Line
              key={g}
              type="monotone"
              dataKey={g}
              stroke={CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === 'area') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            {groups.map((g, i) => (
              <linearGradient key={g} id={`grad-${g}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART_COLORS[i % CHART_COLORS.length]} stopOpacity={0.3} />
                <stop offset="100%" stopColor={CHART_COLORS[i % CHART_COLORS.length]} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="ts" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={formatCompact} tickLine={false} axisLine={false} />
          <Tooltip content={<ChartTooltip />} />
          {groups.length > 1 && <Legend iconType="square" iconSize={10} />}
          {groups.map((g, i) => (
            <Area
              key={g}
              type="monotone"
              dataKey={g}
              stroke={CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2}
              fill={`url(#grad-${g})`}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  if (type === 'bar') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="ts" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={formatCompact} tickLine={false} axisLine={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(10,10,10,0.04)' }} />
          {groups.length > 1 && <Legend iconType="square" iconSize={10} />}
          {groups.map((g, i) => (
            <Bar
              key={g}
              dataKey={g}
              fill={CHART_COLORS[i % CHART_COLORS.length]}
              radius={[3, 3, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (type === 'table') {
    return (
      <div className="overflow-auto" style={{ maxHeight: height }}>
        <table className="w-full text-sm">
          <thead className="border-b border-ink-200">
            <tr>
              <th className="text-left p-2 text-xs uppercase tracking-wide text-ink-500 font-medium">
                {data.granularity ? 'Time' : 'Group'}
              </th>
              <th className="text-right p-2 text-xs uppercase tracking-wide text-ink-500 font-medium">
                Value
              </th>
            </tr>
          </thead>
          <tbody>
            {data.points.map((p, i) => (
              <tr key={i} className="border-b border-ink-100">
                <td className="p-2">
                  {p.group || formatTimestamp(p.timestamp, data.granularity)}
                </td>
                <td className="p-2 text-right font-mono tabular">
                  {formatNumber(p.value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return null;
}

function KPICard({ data }: { data: MetricQueryResult }) {
  const value = data.total;
  const isCount = data.aggregation === 'count' || data.aggregation === 'distinct_count';

  return (
    <div className="flex flex-col justify-center h-full">
      <div className="font-display text-4xl font-medium tabular tracking-tight text-ink-900">
        {isCount ? formatNumber(value) : formatNumber(value, { maximumFractionDigits: 2 })}
      </div>
      <div className="text-xs text-ink-500 mt-2 capitalize">
        {data.aggregation.replace('_', ' ')} · {data.points.length} data point{data.points.length === 1 ? '' : 's'}
      </div>
    </div>
  );
}
