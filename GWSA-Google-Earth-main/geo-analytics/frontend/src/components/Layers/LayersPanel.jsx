import React from 'react';
import { FEATURES } from '../../config/features';
import RailPanel from '../Shell/RailPanel';
import CompetitorSection from './CompetitorSection';
import DemographicsSection from './DemographicsSection';
import LocationsSection from './LocationsSection';

export default function LayersPanel({
  onClose,
  mobile = false,
  dragHandleProps,
  ...locationProps
}) {
  return (
    <RailPanel
      title="Layers"
      description="Toggle what is shown on the map"
      onClose={onClose}
      mobile={mobile}
      dragHandleProps={dragHandleProps}
    >
      <div className="divide-y divide-gwsa-border">
        <LocationsSection {...locationProps} />
        <DemographicsSection />
        <CompetitorSection enabled={FEATURES.competitorLayer} />
      </div>
    </RailPanel>
  );
}
