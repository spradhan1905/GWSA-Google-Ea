import React from 'react';
import { layers24 } from '@esri/calcite-ui-icons/js/layers24.js';
import { wrench24 } from '@esri/calcite-ui-icons/js/wrench24.js';
import { pieChart24 } from '@esri/calcite-ui-icons/js/pieChart24.js';
import { fileReport24 } from '@esri/calcite-ui-icons/js/fileReport24.js';
import { FEATURES } from '../../config/features';
import RailAction from './RailAction';

export const RAIL_ITEMS = [
  {
    id: 'layers',
    label: 'Layers',
    iconPath: layers24,
    enabled: FEATURES.layers,
  },
  {
    id: 'tools',
    label: 'Tools',
    iconPath: wrench24,
    enabled: FEATURES.tools,
  },
  {
    id: 'analytics',
    label: 'Analytics',
    iconPath: pieChart24,
    enabled: FEATURES.analytics,
    soon: !FEATURES.analytics,
  },
  {
    id: 'reports',
    label: 'Reports',
    iconPath: fileReport24,
    enabled: FEATURES.reports,
    soon: !FEATURES.reports,
  },
];

export default function ActionRail({ activeItem, mobile = false, onSelect }) {
  return (
    <nav
      aria-label="Primary"
      className={
        mobile
          ? 'absolute inset-x-0 bottom-0 z-rail flex h-rail items-stretch border-t border-gwsa-border bg-gwsa-surface shadow-panel'
          : 'relative z-rail flex h-full w-rail shrink-0 flex-col items-center gap-1 border-r border-gwsa-border bg-gwsa-surface py-3'
      }
    >
      {RAIL_ITEMS.map((item) => (
        <RailAction
          key={item.id}
          iconPath={item.iconPath}
          label={item.label}
          active={activeItem === item.id}
          disabled={!item.enabled}
          badge={item.soon ? 'Soon' : null}
          mobile={mobile}
          onClick={(event) => {
            if (item.enabled) onSelect(item.id, event.currentTarget);
          }}
        />
      ))}
    </nav>
  );
}
