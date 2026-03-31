/**
 * GWSA GeoAnalytics — TrendChart
 * Recharts line/bar chart component for panel data.
 */
import React from 'react';
import {
  ResponsiveContainer, ComposedChart, Line, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts';

/** Parse YYYY-MM-DD at local noon to avoid UTC shifting the calendar day. */
const parseChartDate = (dateStr) => {
  if (!dateStr) return null;
  const s = String(dateStr);
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d, 12, 0, 0);
  }
  const d = new Date(dateStr);
  return Number.isNaN(d.getTime()) ? null : d;
};

const makeAxisFormatter = (granularity) => (dateStr) => {
  const d = parseChartDate(dateStr);
  if (!d) return '';
  if (granularity === 'day') {
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
  return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
};

const formatTooltipValue = (value, name) => {
  if (typeof value !== 'number') return ['—', name];
  if (name.includes('Ratio')) return [`${(value * 100).toFixed(1)}%`, name];
  if (name.includes('Visits') || name.includes('Door')) return [value.toLocaleString(), name];
  if (value > 1000) return [`$${value.toLocaleString()}`, name];
  return [value.toLocaleString(), name];
};

const CustomTooltip = ({ active, payload, label, formatLabel }) => {
  if (!active || !payload?.length) return null;
  const fmt = formatLabel || makeAxisFormatter('month');
  return (
    <div className="bg-gwsa-surface border border-gwsa-border rounded-lg px-3 py-2 shadow-card">
      <p className="text-xs text-gwsa-text-muted mb-1.5">{fmt(label)}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
          <span className="text-gwsa-text-secondary">{p.name}:</span>
          <span className="font-semibold text-gwsa-text">{formatTooltipValue(p.value, p.name)[0]}</span>
        </div>
      ))}
    </div>
  );
};

export default function TrendChart({
  data = [],
  title,
  lines = [],
  chartType = 'line',
  /** 'day' for daily MTD points; 'month' for monthly PeriodMonth (default). */
  dateAxisGranularity = 'month',
}) {
  if (!data.length) return null;

  const axisFormat = makeAxisFormatter(dateAxisGranularity);

  return (
    <div className="rounded-xl bg-gwsa-bg-alt/50 border border-gwsa-border p-4">
      {title && <h3 className="text-xs font-semibold text-gwsa-text-secondary uppercase tracking-wider mb-3">{title}</h3>}
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1F2A42" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={axisFormat}
            tick={{ fill: '#64748B', fontSize: 10 }}
            axisLine={{ stroke: '#2A3555' }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#64748B', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}
          />
          <Tooltip content={(tipProps) => <CustomTooltip {...tipProps} formatLabel={axisFormat} />} />
          {lines.length > 1 && (
            <Legend
              iconType="circle"
              iconSize={6}
              wrapperStyle={{ fontSize: '10px', color: '#94A3B8', paddingTop: '8px' }}
            />
          )}
          {lines.map((line) => (
            chartType === 'bar' ? (
              <Bar
                key={line.key}
                dataKey={line.key}
                name={line.name}
                fill={line.color}
                fillOpacity={0.7}
                radius={[2, 2, 0, 0]}
                maxBarSize={8}
              />
            ) : (
              <Line
                key={line.key}
                type="monotone"
                dataKey={line.key}
                name={line.name}
                stroke={line.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: line.color, stroke: '#0B0F1A', strokeWidth: 2 }}
              />
            )
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
