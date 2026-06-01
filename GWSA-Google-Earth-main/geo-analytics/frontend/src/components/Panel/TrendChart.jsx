/**
 * GWSA GeoAnalytics — TrendChart
 * Recharts line/bar chart component for panel data.
 */
import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Maximize2, Minimize2 } from 'lucide-react';
import {
  ResponsiveContainer, ComposedChart, Line, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts';

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
  if (name.includes('Visits') || name.includes('Door') || name.includes('Donation')) return [value.toLocaleString(), name];
  if (value > 1000) return [`$${value.toLocaleString()}`, name];
  return [value.toLocaleString(), name];
};

const getMetricUnit = (line) => {
  const name = `${line.name || ''} ${line.key || ''}`;
  if (/ratio|percent|margin/i.test(name)) return 'ratio';
  if (/door|visit|count|donation/i.test(name)) return 'count';
  if (/revenue|income|expense|sales|cost|profit/i.test(name)) return 'currency';
  return 'value';
};

const getAxisFormatter = (unit) => (value) => {
  if (typeof value !== 'number') return value;
  if (unit === 'ratio') return `${Math.round(value * 100)}%`;
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}m`;
  if (value >= 1000) return `${(value / 1000).toFixed(0)}k`;
  return value;
};

const getLineMax = (data, key) => Math.max(
  0,
  ...data
    .map((row) => Number(row?.[key]))
    .filter((value) => Number.isFinite(value))
    .map((value) => Math.abs(value)),
);

const getAxisIdForLine = (line, index, primaryUnit, primaryMax, lineMax, usesDynamicAxes) => {
  if (!usesDynamicAxes || index === 0) return 'primary';

  const unit = getMetricUnit(line);
  const magnitudeGap = primaryMax > 0 && lineMax > 0
    ? Math.max(primaryMax, lineMax) / Math.min(primaryMax, lineMax)
    : 1;

  if (unit !== primaryUnit || magnitudeGap >= 6) {
    return `axis-${line.key}`;
  }
  return 'primary';
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

function ChartBody({
  data,
  title,
  lines,
  chartType,
  dateAxisGranularity,
  chartHeight,
  fullscreenEnabled,
  showFullscreenButton,
  onRequestFullscreen,
  onExitFullscreen,
}) {
  const axisFormat = makeAxisFormatter(dateAxisGranularity);
  const primaryLine = lines[0];
  const primaryUnit = primaryLine ? getMetricUnit(primaryLine) : 'value';
  const primaryMax = primaryLine ? getLineMax(data, primaryLine.key) : 0;
  const usesDynamicAxes = lines.length > 1;
  const linesWithAxes = lines.map((line, index) => {
    const lineMax = getLineMax(data, line.key);
    return {
      ...line,
      unit: getMetricUnit(line),
      yAxisId: getAxisIdForLine(line, index, primaryUnit, primaryMax, lineMax, usesDynamicAxes),
    };
  });
  const secondaryAxes = linesWithAxes.filter((line) => line.yAxisId !== 'primary');

  return (
    <>
      <div className="flex items-start justify-between gap-2 mb-3">
        {title ? (
          <h3 className="text-xs font-semibold text-gwsa-text-secondary uppercase tracking-wider flex-1 min-w-0">
            {title}
          </h3>
        ) : (
          <span />
        )}
        {fullscreenEnabled && showFullscreenButton && (
          <button
            type="button"
            onClick={onRequestFullscreen}
            className="shrink-0 inline-flex items-center justify-center p-1.5 rounded-lg border border-gwsa-border text-gwsa-text-muted hover:text-gwsa-accent hover:border-gwsa-accent/40 transition-colors"
            aria-label="Fullscreen chart"
            title="Fullscreen"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        )}
        {fullscreenEnabled && !showFullscreenButton && onExitFullscreen && (
          <button
            type="button"
            onClick={onExitFullscreen}
            className="shrink-0 inline-flex items-center gap-1.5 px-2 py-1.5 rounded-lg border border-gwsa-border text-xs text-gwsa-text-secondary hover:bg-gwsa-surface-hover"
            aria-label="Exit fullscreen"
          >
            <Minimize2 className="w-3.5 h-3.5" />
            Exit
          </button>
        )}
      </div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <ComposedChart data={data} margin={{ top: 5, right: secondaryAxes.length ? 14 : 5, bottom: 5, left: -10 }}>
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
            yAxisId="primary"
            tick={{ fill: '#64748B', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={getAxisFormatter(primaryUnit)}
          />
          {secondaryAxes.map((line, index) => (
            <YAxis
              key={line.yAxisId}
              yAxisId={line.yAxisId}
              orientation="right"
              axisLine={false}
              tickLine={false}
              tick={{ fill: line.color, fontSize: 10 }}
              tickFormatter={getAxisFormatter(line.unit)}
              width={index === 0 ? 28 : 0}
              hide={index > 0}
            />
          ))}
          <Tooltip content={(tipProps) => <CustomTooltip {...tipProps} formatLabel={axisFormat} />} />
          {lines.length > 1 && (
            <Legend
              iconType="circle"
              iconSize={12}
              wrapperStyle={{ fontSize: '12px', fontWeight: 500, color: '#CBD5E1', paddingTop: '10px' }}
            />
          )}
          {linesWithAxes.map((line) => (
            chartType === 'bar' ? (
              <Bar
                key={line.key}
                dataKey={line.key}
                name={line.name}
                yAxisId={line.yAxisId}
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
                yAxisId={line.yAxisId}
                stroke={line.color}
                strokeWidth={2}
                strokeDasharray={line.dashed ? '5 4' : undefined}
                dot={false}
                activeDot={{ r: 4, fill: line.color, stroke: '#0B0F1A', strokeWidth: 2 }}
              />
            )
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}

export default function TrendChart({
  data = [],
  title,
  lines = [],
  chartType = 'line',
  dateAxisGranularity = 'month',
  fullscreenEnabled = true,
  fullscreenChartHeight = 420,
  embeddedChartHeight = 200,
}) {
  const [fullscreenOpen, setFullscreenOpen] = useState(false);

  useEffect(() => {
    if (!fullscreenOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') setFullscreenOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [fullscreenOpen]);

  useEffect(() => {
    if (fullscreenOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [fullscreenOpen]);

  if (!data.length) return null;

  const chartProps = {
    data,
    title,
    lines,
    chartType,
    dateAxisGranularity,
    fullscreenEnabled,
  };

  return (
    <>
      <div className="rounded-xl bg-gwsa-bg-alt/50 border border-gwsa-border p-4">
        <ChartBody
          {...chartProps}
          chartHeight={embeddedChartHeight}
          showFullscreenButton
          onRequestFullscreen={() => setFullscreenOpen(true)}
        />
      </div>
      {fullscreenEnabled &&
        fullscreenOpen &&
        createPortal(
          <div
            className="fixed inset-0 z-[400] flex flex-col bg-gwsa-bg/98 backdrop-blur-sm"
            role="dialog"
            aria-modal="true"
            aria-label="Chart fullscreen"
          >
            <div className="flex-1 min-h-0 p-4 sm:p-8 overflow-auto">
              <div className="max-w-6xl mx-auto h-full min-h-[min(70vh,600px)] rounded-xl border border-gwsa-border bg-gwsa-surface/80 p-4 sm:p-6">
                <ChartBody
                  {...chartProps}
                  chartHeight={fullscreenChartHeight}
                  showFullscreenButton={false}
                  onExitFullscreen={() => setFullscreenOpen(false)}
                />
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
