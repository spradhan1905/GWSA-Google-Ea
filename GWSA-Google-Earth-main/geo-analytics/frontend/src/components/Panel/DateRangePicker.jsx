/**
 * GWSA GeoAnalytics — DateRangePicker
 * Quick presets + custom range via calendar control.
 */
import React, { useState, useEffect, useRef } from 'react';
import { Calendar } from 'lucide-react';
import { localDateISO } from '../../utils/dateUtils';

const PRESETS = [
  { label: 'This Month', months: 1 },
  { label: 'Quarter', months: 3 },
  { label: 'YTD', months: 0 }, // special
  { label: '12 Months', months: 12 },
];

export default function DateRangePicker({ dateRange, onChange, preset: activePreset = 'This Month' }) {
  const [customOpen, setCustomOpen] = useState(false);
  const [draftStart, setDraftStart] = useState(dateRange?.start || '');
  const [draftEnd, setDraftEnd] = useState(dateRange?.end || '');
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!customOpen) return;
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setCustomOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setCustomOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [customOpen]);

  const applyPreset = (preset) => {
    setCustomOpen(false);
    let end = new Date();
    let start;
    if (preset.label === 'YTD') {
      start = new Date(end.getFullYear(), 0, 1);
    } else if (preset.label === 'This Month') {
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

  const applyCustom = () => {
    let a = (draftStart || '').trim();
    let b = (draftEnd || '').trim();
    if (!a || !b) return;
    if (a > b) {
      const t = a;
      a = b;
      b = t;
    }
    onChange({
      start: a,
      end: b,
      preset: 'Custom',
    });
    setCustomOpen(false);
  };

  const customActive = activePreset === 'Custom';

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <div className="relative inline-flex" ref={wrapRef}>
        <button
          type="button"
          onClick={() => {
            setCustomOpen((o) => {
              if (!o) {
                setDraftStart(dateRange.start);
                setDraftEnd(dateRange.end);
              }
              return !o;
            });
          }}
          aria-expanded={customOpen}
          aria-haspopup="dialog"
          aria-label="Select custom date range"
          title="Custom date range"
          className={`inline-flex items-center justify-center p-1.5 rounded-md border transition-all duration-200 ${
            customActive || customOpen
              ? 'bg-gwsa-accent/20 text-gwsa-accent border border-gwsa-accent/30'
              : 'text-gwsa-text-muted hover:text-gwsa-text-secondary hover:bg-gwsa-surface-hover border border-transparent'
          }`}
        >
          <Calendar className="w-3.5 h-3.5 shrink-0" strokeWidth={2} />
        </button>
        {customOpen && (
          <div
            role="dialog"
            aria-label="Custom date range"
            className="absolute top-full left-0 z-50 mt-1 min-w-[220px] rounded-lg border border-gwsa-border bg-gwsa-surface p-3 shadow-panel"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <p className="text-[10px] font-semibold uppercase tracking-wide text-gwsa-text-muted mb-2">
              Date range
            </p>
            <div className="flex flex-col gap-2">
              <label className="flex flex-col gap-0.5">
                <span className="text-[11px] text-gwsa-text-muted">Start</span>
                <input
                  type="date"
                  value={draftStart}
                  onChange={(e) => setDraftStart(e.target.value)}
                  className="text-xs rounded-md border border-gwsa-border bg-gwsa-bg px-2 py-1.5 text-gwsa-text-secondary"
                />
              </label>
              <label className="flex flex-col gap-0.5">
                <span className="text-[11px] text-gwsa-text-muted">End</span>
                <input
                  type="date"
                  value={draftEnd}
                  min={draftStart || undefined}
                  onChange={(e) => setDraftEnd(e.target.value)}
                  className="text-xs rounded-md border border-gwsa-border bg-gwsa-bg px-2 py-1.5 text-gwsa-text-secondary"
                />
              </label>
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCustomOpen(false)}
                className="text-[11px] px-2 py-1 rounded-md text-gwsa-text-muted hover:bg-gwsa-surface-hover"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={applyCustom}
                disabled={!draftStart || !draftEnd}
                className="text-[11px] px-2.5 py-1 rounded-md font-medium bg-gwsa-accent/20 text-gwsa-accent border border-gwsa-accent/30 hover:bg-gwsa-accent/30 disabled:opacity-40 disabled:pointer-events-none"
              >
                Apply
              </button>
            </div>
          </div>
        )}
      </div>
      {PRESETS.map((p) => (
        <button key={p.label} type="button" onClick={() => applyPreset(p)}
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
