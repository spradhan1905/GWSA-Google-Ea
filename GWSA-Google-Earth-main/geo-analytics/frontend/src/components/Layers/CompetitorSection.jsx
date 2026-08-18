import React from 'react';
import { Lock, Store } from 'lucide-react';

export default function CompetitorSection({ enabled = false }) {
  return (
    <section
      className={`px-4 py-3.5 ${enabled ? '' : 'opacity-60'}`}
      aria-labelledby="competitor-layer-title"
      aria-disabled={!enabled}
    >
      <div className="flex items-center gap-2">
        <Store className="h-4 w-4 text-gwsa-text-muted" strokeWidth={1.75} aria-hidden />
        <h3 id="competitor-layer-title" className="text-sm font-semibold text-gwsa-text">
          Competitor Locations
        </h3>
        {!enabled && (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-gwsa-soon/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
            <Lock className="h-2.5 w-2.5" aria-hidden /> Soon
          </span>
        )}
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-gwsa-text-muted">
        {enabled
          ? 'No competitor locations are available yet.'
          : 'Nearby thrift and donation competitor sites will appear here once the data source is connected.'}
      </p>
    </section>
  );
}
