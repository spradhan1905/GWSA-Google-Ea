import React from 'react';
import { caretDown24 } from '@esri/calcite-ui-icons/js/caretDown24.js';
import { mapPin24 } from '@esri/calcite-ui-icons/js/mapPin24.js';
import StoreList from '../StoreList/StoreList';
import CalciteIcon from '../Shell/CalciteIcon';

export default function LocationsSection(props) {
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3.5 text-sm font-semibold text-gwsa-text hover:bg-gwsa-surface-hover">
        <CalciteIcon path={mapPin24} className="h-4 w-4 text-gwsa-accent" />
        <span>Locations</span>
        <span className="ml-auto rounded-full bg-gwsa-bg-alt px-2 py-0.5 text-[10px] font-semibold text-gwsa-text-secondary">
          {props.locations?.length ?? 0}
        </span>
        <CalciteIcon path={caretDown24} className="h-3 w-3 text-gwsa-text-muted transition-transform group-open:rotate-180" />
      </summary>
      <StoreList {...props} embedded onCollapse={undefined} dragHandleProps={undefined} />
    </details>
  );
}
