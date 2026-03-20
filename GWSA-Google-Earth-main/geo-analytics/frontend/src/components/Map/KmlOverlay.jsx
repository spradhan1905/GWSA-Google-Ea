/**
 * GWSA GeoAnalytics — KML Overlay
 * Renders gwsa-geo.kml layer on the map. Suppresses default info windows;
 * click events are forwarded so the app can open the side panel or show tooltips.
 */
import React, { useEffect, useRef } from 'react';

const KML_URL = '/gwsa-geo.kml';

export default function KmlOverlay({ map, onKmlClick }) {
  const layerRef = useRef(null);

  useEffect(() => {
    if (!map || !window.google?.maps) return;

    try {
      const kmlLayer = new window.google.maps.KmlLayer({
        url: `${window.location.origin}${KML_URL}`,
        map,
        suppressInfoWindows: true,
        preserveViewport: false,
      });

      if (typeof onKmlClick === 'function') {
        kmlLayer.addListener('click', (event) => {
          const name = event.featureData?.name || event.featureData?.description || '';
          const latLng = event.latLng;
          if (name || latLng) onKmlClick(name, latLng);
        });
      }

      layerRef.current = kmlLayer;
      return () => {
        if (layerRef.current) {
          layerRef.current.setMap(null);
          layerRef.current = null;
        }
      };
    } catch (err) {
      console.warn('[KmlOverlay] Could not load KML layer:', err.message);
    }
  }, [map, onKmlClick]);

  return null;
}
