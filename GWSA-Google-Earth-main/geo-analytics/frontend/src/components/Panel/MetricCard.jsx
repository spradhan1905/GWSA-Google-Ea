/**
 * GWSA GeoAnalytics — MetricCard
 * Single KPI card with value, label, optional change indicator.
 */
import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const COLOR_MAP = {
  blue: 'border-l-gwsa-accent',
  green: 'border-l-emerald-600',
  amber: 'border-l-amber-600',
  cyan: 'border-l-cyan-700',
  purple: 'border-l-purple-700',
  red: 'border-l-red-700',
};

export default function MetricCard({ label, value, change, color = 'blue', subtext }) {
  const accentBorder = COLOR_MAP[color] || COLOR_MAP.blue;

  return (
    <div className={`rounded-md border border-gwsa-border border-l-2 bg-gwsa-surface p-3.5 shadow-card ${accentBorder}`}>
      <p className="metric-label mb-1 text-gwsa-text-secondary">{label}</p>
      <p className="metric-value text-gwsa-text">{value}</p>
      {change && (
        <div className={`flex items-center gap-1 mt-1.5 text-xs font-medium ${
          change.direction === 'up' ? 'text-emerald-700' : change.direction === 'down' ? 'text-red-700' : 'text-gwsa-text-muted'
        }`}>
          {change.direction === 'up' ? <TrendingUp className="w-3 h-3" /> :
           change.direction === 'down' ? <TrendingDown className="w-3 h-3" /> :
           <Minus className="w-3 h-3" />}
          <span>{change.percent}% vs prior</span>
        </div>
      )}
      {subtext && <p className="text-[10px] text-gwsa-text-muted mt-1">{subtext}</p>}
    </div>
  );
}
