/**
 * GWSA GeoAnalytics — DateRangePicker
 * Quick presets + custom date inputs.
 */
import React from 'react';
import { Calendar } from 'lucide-react';
import { localDateISO } from '../../utils/dateUtils';

const PRESETS = [
  { label: 'This Month', months: 1 },
  { label: 'Quarter', months: 3 },
  { label: 'YTD', months: 0 }, // special
  { label: '12 Months', months: 12 },
];

export default function DateRangePicker({ dateRange, onChange, preset: activePreset = 'This Month' }) {
  const applyPreset = (preset) => {
    const end = new Date();
    let start;
    if (preset.label === 'YTD') {
      start = new Date(end.getFullYear(), 0, 1);
    } else if (preset.label === 'This Month') {
      // Calendar month to date (not "previous month")
      start = new Date(end.getFullYear(), end.getMonth(), 1);
    } else {
      start = new Date();
      start.setMonth(start.getMonth() - preset.months);
      start.setDate(1);
    }
    onChange({
      start: localDateISO(start),
      end: localDateISO(end),
      preset: preset.label,
    });
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Calendar className="w-3.5 h-3.5 text-gwsa-text-muted shrink-0" />
      {PRESETS.map((p) => (
        <button key={p.label} onClick={() => applyPreset(p)}
          className={`text-[11px] px-2 py-1 rounded-md font-medium transition-all duration-200 ${
            activePreset === p.label
              ? 'bg-gwsa-accent/20 text-gwsa-accent border border-gwsa-accent/30'
              : 'text-gwsa-text-muted hover:text-gwsa-text-secondary hover:bg-gwsa-surface-hover border border-transparent'
          }`}>
          {p.label}
        </button>
      ))}
    </div>
  );
}
