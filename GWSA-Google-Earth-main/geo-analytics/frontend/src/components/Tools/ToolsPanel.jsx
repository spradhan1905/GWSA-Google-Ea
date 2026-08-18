import React from 'react';
import { basemap24 } from '@esri/calcite-ui-icons/js/basemap24.js';
import { cube24 } from '@esri/calcite-ui-icons/js/cube24.js';
import { map24 } from '@esri/calcite-ui-icons/js/map24.js';
import { measure24 } from '@esri/calcite-ui-icons/js/measure24.js';
import { reset24 } from '@esri/calcite-ui-icons/js/reset24.js';
import { useMapControls } from '../../context/MapControlsContext';
import CalciteIcon from '../Shell/CalciteIcon';
import RailPanel from '../Shell/RailPanel';

function ToolButton({ iconPath, title, description, active = false, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex w-full items-center gap-3 p-3 text-left transition-colors ${
        active
          ? 'bg-gwsa-rail-active-bg text-gwsa-accent'
          : 'bg-gwsa-surface text-gwsa-text hover:bg-gwsa-surface-hover'
      }`}
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-gwsa-bg-alt">
        <CalciteIcon path={iconPath} className="h-4 w-4" />
      </span>
      <span>
        <span className="block text-sm font-semibold">{title}</span>
        <span className="mt-0.5 block text-xs text-gwsa-text-muted">{description}</span>
      </span>
    </button>
  );
}

export default function ToolsPanel({ onClose, mobile = false, dragHandleProps }) {
  const {
    activeTool,
    setActiveTool,
    is3D,
    setIs3D,
    mapTypeId,
    setMapTypeId,
    requestResetView,
  } = useMapControls();
  const satelliteSelected = mapTypeId === 'hybrid' || mapTypeId === 'satellite';

  return (
    <RailPanel
      title="Tools"
      description="Explore and interact with the map"
      onClose={onClose}
      mobile={mobile}
      dragHandleProps={dragHandleProps}
    >
      <div className="space-y-4 p-4">
        <div className="divide-y divide-gwsa-border overflow-hidden rounded-md border border-gwsa-border">
          <ToolButton
            iconPath={measure24}
            title="Measure distance"
            description={activeTool === 'measure' ? 'Click map points to measure. Select again to clear.' : 'Plot a path between points on the map.'}
            active={activeTool === 'measure'}
            onClick={() => setActiveTool((tool) => tool === 'measure' ? 'none' : 'measure')}
          />
          <ToolButton
            iconPath={cube24}
            title="3D view"
            description="Tilt the satellite map for perspective."
            active={is3D}
            onClick={() => setIs3D((enabled) => !enabled)}
          />
          <ToolButton
            iconPath={reset24}
            title="Reset view"
            description="Return to the default San Antonio view."
            onClick={requestResetView}
          />
        </div>

        <fieldset className="rounded-md border border-gwsa-border p-3">
          <legend className="px-1 text-sm font-semibold text-gwsa-text">Basemap</legend>
          <div className="mt-2 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-gwsa-border bg-gwsa-border">
            <button
              type="button"
              onClick={() => setMapTypeId('hybrid')}
              aria-pressed={satelliteSelected}
              className={`flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold ${
                satelliteSelected
                  ? 'bg-gwsa-accent text-white'
                  : 'bg-gwsa-bg-alt text-gwsa-text-secondary hover:text-gwsa-text'
              }`}
            >
              <CalciteIcon path={basemap24} className="h-4 w-4" /> Satellite
            </button>
            <button
              type="button"
              onClick={() => setMapTypeId('roadmap')}
              aria-pressed={mapTypeId === 'roadmap'}
              className={`flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold ${
                mapTypeId === 'roadmap'
                  ? 'bg-gwsa-accent text-white'
                  : 'bg-gwsa-bg-alt text-gwsa-text-secondary hover:text-gwsa-text'
              }`}
            >
              <CalciteIcon path={map24} className="h-4 w-4" /> Map
            </button>
          </div>
        </fieldset>
      </div>
    </RailPanel>
  );
}
