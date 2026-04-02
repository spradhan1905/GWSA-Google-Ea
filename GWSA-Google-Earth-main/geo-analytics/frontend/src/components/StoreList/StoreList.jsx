/**
 * GWSA GeoAnalytics — Store List (left panel)
 * Per store locator UX: list on left, map on right. Filters, count, Get Directions.
 * @see https://uxleash.com/store-locator-ux-best-practices-boost-engagement-conversions/
 */
import React from 'react';
import { ExternalLink, ChevronRight, PanelLeftClose } from 'lucide-react';
import { LOCATION_TYPE_CONFIG, LOCATION_TYPE_FALLBACK } from '../../data/stores';

const TYPE_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'store', label: 'Retail' },
  { id: 'adc', label: 'Donation' },
  { id: 'outlet', label: 'Outlet' },
  { id: 'dropbox', label: 'Drop Box' },
];

function getDirectionsUrl(loc) {
  if (loc.lat != null && loc.lng != null) {
    return `https://www.waze.com/ul?ll=${loc.lat},${loc.lng}&navigate=yes`;
  }
  if (loc.address) {
    return `https://www.waze.com/ul?q=${encodeURIComponent(loc.address)}&navigate=yes`;
  }
  return '#';
}

export default function StoreList({
  locations = [],
  selectedLocation,
  onSelectLocation,
  typeFilter,
  onTypeFilterChange,
  onCollapse,
}) {
  const cfgAll = LOCATION_TYPE_CONFIG;

  return (
    <div className="h-full flex flex-col bg-gwsa-surface/95 backdrop-blur-sm border-r border-gwsa-border w-full sm:w-[360px] shrink-0 overflow-hidden">
      {/* Header: location context + count + collapse */}
      <div className="shrink-0 px-4 pt-4 pb-3 border-b border-gwsa-border flex items-center justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-gwsa-text-muted uppercase tracking-wider">
            San Antonio & South Texas
          </p>
          <p className="text-lg font-bold text-gwsa-text mt-0.5">
            {locations.length} {locations.length === 1 ? 'location' : 'locations'} found
          </p>
        </div>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-gwsa-bg-alt border border-gwsa-border text-gwsa-text-secondary hover:text-gwsa-text hover:border-gwsa-border-light"
          >
            <PanelLeftClose className="w-3.5 h-3.5" />
            Hide
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="shrink-0 px-4 py-3 border-b border-gwsa-border">
        <p className="text-xs text-gwsa-text-muted mb-2">Filter by type</p>
        <div className="flex flex-wrap gap-1.5">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => onTypeFilterChange(f.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                typeFilter === f.id
                  ? 'bg-gwsa-accent text-white shadow-glow'
                  : 'bg-gwsa-bg-alt border border-gwsa-border text-gwsa-text-secondary hover:text-gwsa-text hover:border-gwsa-border-light'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Scrollable list */}
      <div className="flex-1 overflow-y-auto">
        <ul className="divide-y divide-gwsa-border">
          {locations.map((loc) => {
            const cfg = cfgAll[loc.type] || LOCATION_TYPE_FALLBACK;
            const TypeIcon = cfg.Icon || LOCATION_TYPE_FALLBACK.Icon;
            const isSelected = selectedLocation?.id === loc.id;
            return (
              <li key={loc.id}>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectLocation(loc)}
                  onKeyDown={(e) => e.key === 'Enter' && onSelectLocation(loc)}
                  className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-all duration-200 ${
                    isSelected
                      ? 'bg-gwsa-accent/15 border-l-4 border-gwsa-accent -ml-px pl-[calc(1rem-1px)]'
                      : 'hover:bg-gwsa-surface-hover'
                  }`}
                >
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ backgroundColor: `${cfg.color}20`, color: cfg.color }}
                  >
                    <TypeIcon className="w-5 h-5" strokeWidth={1.75} aria-hidden />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gwsa-text truncate">{loc.name}</p>
                    <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                      <span
                        className="inline-flex text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full"
                        style={{ backgroundColor: `${cfg.color}20`, color: cfg.color }}
                      >
                        {cfg.label}
                      </span>
                    </div>
                    {getDirectionsUrl(loc) !== '#' && (
                      <a
                        href={getDirectionsUrl(loc)}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-gwsa-accent hover:text-gwsa-accent-hover"
                      >
                        <ExternalLink className="w-3 h-3" />
                        Get Directions
                      </a>
                    )}
                  </div>
                  <ChevronRight
                    className={`w-4 h-4 shrink-0 mt-1 ${
                      isSelected ? 'text-gwsa-accent' : 'text-gwsa-text-muted'
                    }`}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
