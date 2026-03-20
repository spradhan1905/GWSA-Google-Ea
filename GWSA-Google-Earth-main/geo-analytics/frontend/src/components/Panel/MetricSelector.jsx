/**
 * GWSA GeoAnalytics — MetricSelector
 * Tab switcher for panel sections.
 */
import React from 'react';

export default function MetricSelector({ tabs = [], activeTab, onTabChange }) {
  return (
    <div className="shrink-0 flex border-b border-gwsa-border px-5">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-all duration-200 border-b-2 -mb-[1px] ${
              isActive
                ? 'text-gwsa-accent border-gwsa-accent'
                : 'text-gwsa-text-muted border-transparent hover:text-gwsa-text-secondary hover:border-gwsa-border-light'
            }`}
          >
            {Icon && <Icon className="w-3.5 h-3.5" />}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
