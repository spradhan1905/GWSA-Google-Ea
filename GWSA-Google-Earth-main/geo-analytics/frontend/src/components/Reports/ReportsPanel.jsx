import React from 'react';
import { fileReport24 } from '@esri/calcite-ui-icons/js/fileReport24.js';
import CalciteIcon from '../Shell/CalciteIcon';
import RailPanel from '../Shell/RailPanel';

export default function ReportsPanel({ onClose, mobile = false, dragHandleProps }) {
  return (
    <RailPanel
      title="Reports"
      description="Create exportable location summaries"
      onClose={onClose}
      mobile={mobile}
      dragHandleProps={dragHandleProps}
    >
      <div className="flex h-full flex-col items-center justify-center px-8 py-12 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-md bg-gwsa-rail-active-bg text-gwsa-accent">
          <CalciteIcon path={fileReport24} className="h-6 w-6" />
        </span>
        <h3 className="mt-4 text-sm font-semibold text-gwsa-text">Reports are coming soon</h3>
        <p className="mt-2 text-xs leading-relaxed text-gwsa-text-muted">
          Exportable location and portfolio summaries will appear here when reporting is available.
        </p>
      </div>
    </RailPanel>
  );
}
