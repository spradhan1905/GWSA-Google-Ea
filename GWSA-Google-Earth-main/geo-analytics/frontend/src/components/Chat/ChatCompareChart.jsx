/**
 * Renders structured chart payloads from POST /api/chat/stream meta.chart
 */
import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

function shortStoreName(name) {
  if (!name) return '';
  return String(name)
    .replace(/\s+Retail Store$/i, '')
    .replace(/\s+Donation Station$/i, '')
    .replace(/\s+Outlet Retail Store$/i, ' Outlet')
    .trim();
}

function formatValue(metric, value) {
  const n = Number(value);
  if (Number.isNaN(n)) return String(value ?? '');
  const m = (metric || '').toLowerCase();
  if (m === 'door_count') return n.toLocaleString();
  if (m === 'donations' || m === 'revenue' || m.includes('income') || m.includes('expense')) {
    return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  return n.toLocaleString();
}

export default function ChatCompareChart({ chart }) {
  if (!chart || !Array.isArray(chart.rows) || chart.rows.length === 0) {
    return null;
  }

  const xKey = chart.x_key || 'location_name';
  const yKey = chart.y_key || 'metric_value';
  const metric = chart.y_label || chart.metric || 'value';

  const data = chart.rows.map((row) => {
    const rawLabel =
      row.category
      ?? row.location_name
      ?? row.label
      ?? row.date
      ?? row[xKey]
      ?? '';
    const rawValue =
      row.revenue
      ?? row.metric_value
      ?? row.value
      ?? row.NetRevenue
      ?? row[yKey]
      ?? 0;
    const num = Number(rawValue);
    const isStoreLabel = /retail store|donation station/i.test(String(rawLabel));
    return {
      ...row,
      label: isStoreLabel ? shortStoreName(rawLabel) || rawLabel : String(rawLabel),
      value: Number.isFinite(num) ? num : 0,
    };
  }).filter((d) => d.value > 0 && d.label);

  if (data.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 rounded-lg border border-gwsa-border bg-gwsa-bg p-2">
      {chart.title ? (
        <p className="text-[10px] font-medium text-gwsa-text-secondary mb-2 px-1">{chart.title}</p>
      ) : null}
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--gwsa-border, #e5e7eb)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: 'var(--gwsa-text-muted, #6b7280)' }}
            interval={0}
            angle={data.length > 3 ? -18 : 0}
            textAnchor={data.length > 3 ? 'end' : 'middle'}
            height={data.length > 3 ? 48 : 28}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--gwsa-text-muted, #6b7280)' }}
            tickFormatter={(v) => formatValue(metric, v)}
            width={56}
          />
          <Tooltip
            formatter={(v) => [formatValue(metric, v), metric.replace(/_/g, ' ')]}
            labelFormatter={(l) => l}
            contentStyle={{ fontSize: 11 }}
          />
          <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
