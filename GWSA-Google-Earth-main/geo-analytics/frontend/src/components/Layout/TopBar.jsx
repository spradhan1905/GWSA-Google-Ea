/**
 * GWSA GeoAnalytics — TopBar
 * App header with logo, store search, and AI chat toggle.
 */
import React, { useState, useRef, useEffect } from 'react';
import { Search, X, MapPin, Sparkles, ArrowLeft } from 'lucide-react';
import { LOCATION_TYPE_CONFIG, LOCATION_TYPE_FALLBACK } from '../../data/stores';

const GWSA_LOGO_URL = '/assets/goodwill-san-antonio-logo.png';

export default function TopBar({
  locations = [],
  searchQuery,
  onSearchChange,
  onSearchSelect,
  onChatToggle,
  chatOpen,
  aiEnabled = true,
  onBackToLanding,
}) {
  const [focused, setFocused] = useState(false);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  const filtered = searchQuery
    ? locations.filter(l =>
        l.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        l.type.toLowerCase().includes(searchQuery.toLowerCase())
      ).slice(0, 8)
    : [];

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target) &&
          inputRef.current && !inputRef.current.contains(e.target)) {
        setFocused(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <header className="h-14 bg-gwsa-surface border-b border-gwsa-border flex items-center px-4 gap-4 z-50 shrink-0">
      {/* Logo + back */}
      <div className="flex items-center gap-2.5 shrink-0">
        {onBackToLanding && (
          <button
            type="button"
            onClick={onBackToLanding}
            className="mr-1 rounded-sm border border-gwsa-border bg-gwsa-surface p-1.5 text-gwsa-text-muted hover:bg-gwsa-surface-hover hover:text-gwsa-text"
            title="Back to overview"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
        )}
        <div className="flex h-8 w-8 items-center justify-center overflow-hidden bg-white">
          <img
            src={GWSA_LOGO_URL}
            alt=""
            className="w-full h-full object-contain"
            aria-hidden
          />
        </div>
        <div className="hidden sm:block">
          <h1 className="text-sm font-semibold leading-tight text-gwsa-text">
            GWSA GeoAnalytics
          </h1>
          <p className="text-[10px] text-gwsa-text-muted leading-tight">
            Goodwill Industries of San Antonio
          </p>
        </div>
      </div>

      {/* Search — flexible input: name, city, manager */}
      <div className="flex-1 max-w-lg relative">
        <div className={`flex h-9 items-center rounded-md border transition-colors ${
          focused ? 'border-gwsa-accent bg-gwsa-bg-alt shadow-glow' : 'border-gwsa-border bg-gwsa-bg-alt/50'
        }`}>
          <Search className="w-3.5 h-3.5 text-gwsa-text-muted ml-3 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search by store name or type..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            onFocus={() => setFocused(true)}
            className="flex-1 bg-transparent border-none text-sm text-gwsa-text placeholder:text-gwsa-text-muted px-2 py-0 focus:outline-none focus:ring-0"
          />
          {searchQuery && (
            <button onClick={() => onSearchChange('')} className="p-1 mr-1 rounded hover:bg-gwsa-surface-hover">
              <X className="w-3.5 h-3.5 text-gwsa-text-muted" />
            </button>
          )}
        </div>

        {/* Search dropdown */}
        {focused && searchQuery && filtered.length > 0 && (
          <div ref={dropdownRef} className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-md border border-gwsa-border bg-gwsa-surface shadow-panel animate-fade-in">
            {filtered.map((loc) => {
              const cfg = LOCATION_TYPE_CONFIG[loc.type] || LOCATION_TYPE_FALLBACK;
              const TypeIcon = cfg.Icon || LOCATION_TYPE_FALLBACK.Icon;
              return (
                <button
                  key={loc.id}
                  onClick={() => {
                    onSearchSelect(loc);
                    onSearchChange('');
                    setFocused(false);
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gwsa-surface-hover transition-colors text-left"
                >
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-sm"
                    style={{ backgroundColor: `${cfg.color}20`, color: cfg.color }}>
                    {cfg.marker ? (
                      <img
                        src={cfg.marker.url}
                        alt=""
                        className="w-5 h-5 object-contain"
                        aria-hidden
                      />
                    ) : (
                      <TypeIcon className="w-4 h-4" strokeWidth={1.75} aria-hidden />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gwsa-text truncate">{loc.name}</p>
                    <p className="text-xs text-gwsa-text-muted">
                      {cfg.label}
                    </p>
                  </div>
                  <MapPin className="w-3.5 h-3.5 text-gwsa-text-muted shrink-0" />
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* AI Chat Toggle */}
      {aiEnabled && (
        <button
          onClick={onChatToggle}
          className={`flex h-9 shrink-0 items-center gap-2 rounded-md px-3.5 text-sm font-medium transition-colors ${
            chatOpen
              ? 'bg-gwsa-accent text-white shadow-glow'
              : 'bg-gwsa-bg-alt border border-gwsa-border text-gwsa-text-secondary hover:text-gwsa-text hover:border-gwsa-border-light'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span className="hidden sm:inline">Ask AI</span>
        </button>
      )}
    </header>
  );
}
