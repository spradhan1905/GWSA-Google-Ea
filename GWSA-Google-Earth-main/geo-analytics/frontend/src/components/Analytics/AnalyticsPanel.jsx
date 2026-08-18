import React from 'react';
import { pieChart24 } from '@esri/calcite-ui-icons/js/pieChart24.js';
import CalciteIcon from '../Shell/CalciteIcon';
import RailPanel from '../Shell/RailPanel';

export default function AnalyticsPanel({ onClose, mobile = false, dragHandleProps }) {
  return (
    <RailPanel
      title="Portfolio Analytics"
      description="Compare performance across locations"
      onClose={onClose}
      mobile={mobile}
      dragHandleProps={dragHandleProps}
    >
      <div className="flex h-full flex-col items-center justify-center px-8 py-12 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-md bg-gwsa-rail-active-bg text-gwsa-accent">
          <CalciteIcon path={pieChart24} className="h-6 w-6" />
        </span>
        <h3 className="mt-4 text-sm font-semibold text-gwsa-text">Portfolio analytics are coming soon</h3>
        <p className="mt-2 text-xs leading-relaxed text-gwsa-text-muted">
          Cross-location comparisons, rankings, and portfolio trends will appear here when the analytics service is ready.
        </p>
      </div>
    </RailPanel>
  );
}
