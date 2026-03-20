/**
 * GWSA GeoAnalytics — MetricCard
 * Single KPI card with value, label, optional change indicator.
 */
import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const COLOR_MAP = {
  blue:   { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20' },
  green:  { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20' },
  amber:  { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20' },
  cyan:   { bg: 'bg-cyan-500/10', text: 'text-cyan-400', border: 'border-cyan-500/20' },
  purple: { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20' },
  red:    { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20' },
};

export default function MetricCard({ label, value, change, color = 'blue', subtext }) {
  const c = COLOR_MAP[color] || COLOR_MAP.blue;

  return (
    <div className={`rounded-xl ${c.bg} border ${c.border} p-3.5 transition-all duration-200 hover:scale-[1.02]`}>
      <p className="metric-label text-gwsa-text-muted mb-1">{label}</p>
      <p className={`metric-value ${c.text}`}>{value}</p>
      {change && (
        <div className={`flex items-center gap-1 mt-1.5 text-xs font-medium ${
          change.direction === 'up' ? 'text-emerald-400' : change.direction === 'down' ? 'text-red-400' : 'text-gwsa-text-muted'
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
