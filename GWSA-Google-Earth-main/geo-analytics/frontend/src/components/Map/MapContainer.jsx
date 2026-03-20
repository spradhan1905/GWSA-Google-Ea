/**
 * GWSA GeoAnalytics — Map Container
 * Google Maps satellite view centered on San Antonio.
 * Renders location pins with custom markers and optional KML overlay.
 */
import React, { useRef, useEffect, useState, useCallback } from 'react';
import { RotateCcw, Ruler, Box } from 'lucide-react';
import { LOCATION_TYPE_CONFIG } from '../../data/stores';
import KmlOverlay from './KmlOverlay';

const MAP_CENTER = { lat: 29.4241, lng: -98.4936 };
// Slightly closer default zoom so 3D buildings and roads feel crisper.
const MAP_ZOOM = 12;

// Use Google's default satellite styling for a clean, modern look.
// Leaving this array empty means we don't override Google's visual design.
const MAP_STYLES = [];

function createMarkerSVG(type, isSelected) {
  const cfg = LOCATION_TYPE_CONFIG[type] || { color: '#3B82F6', icon: '📍' };
  const color = cfg.color;
  const size = isSelected ? 44 : 36;
  const glow = isSelected ? `<circle cx="${size/2}" cy="${size/2}" r="${size/2}" fill="${color}" opacity="0.25"/>` : '';

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size+8}" viewBox="0 0 ${size} ${size+8}">
      ${glow}
      <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="rgba(0,0,0,0.4)"/>
        </filter>
      </defs>
      <circle cx="${size/2}" cy="${size/2}" r="${size/2 - 3}" fill="${color}" filter="url(#shadow)" stroke="white" stroke-width="2"/>
      <text x="${size/2}" y="${size/2 + 1}" text-anchor="middle" dominant-baseline="central" font-size="${size * 0.4}">${cfg.icon}</text>
      <polygon points="${size/2 - 5},${size - 3} ${size/2},${size + 5} ${size/2 + 5},${size - 3}" fill="${color}"/>
    </svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export default function MapContainer({ locations = [], selectedLocation, onPinClick }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const geocoderRef = useRef(null);
  const geocodeCacheRef = useRef({});
  const [mapReady, setMapReady] = useState(false);
  const [activeTool, setActiveTool] = useState('none'); // 'none' | 'measure'
  const [is3D, setIs3D] = useState(false);
  const measurePolylineRef = useRef(null);
  const measurePathRef = useRef([]);
  const measureClickListenerRef = useRef(null);

  // Initialize Google Map
  useEffect(() => {
    if (!window.google?.maps || mapInstanceRef.current) return;

    const map = new window.google.maps.Map(mapRef.current, {
      center: MAP_CENTER,
      zoom: MAP_ZOOM,
      mapTypeId: 'hybrid',
      tilt: 0,
      mapTypeControl: true,
      mapTypeControlOptions: {
        style: window.google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
        position: window.google.maps.ControlPosition.TOP_LEFT,
        mapTypeIds: ['hybrid', 'satellite', 'roadmap'],
      },
      streetViewControl: false,
      fullscreenControl: true,
      fullscreenControlOptions: { position: window.google.maps.ControlPosition.RIGHT_TOP },
      zoomControl: true,
      zoomControlOptions: { position: window.google.maps.ControlPosition.RIGHT_CENTER },
      rotateControl: true,
      styles: MAP_STYLES,
      gestureHandling: 'greedy',
    });

    mapInstanceRef.current = map;
    geocoderRef.current = new window.google.maps.Geocoder();
    setMapReady(true);
  }, []);

  // Fallback: retry if google maps loads late
  useEffect(() => {
    if (mapInstanceRef.current) return;
    const interval = setInterval(() => {
      if (window.google?.maps && !mapInstanceRef.current) {
        const map = new window.google.maps.Map(mapRef.current, {
          center: MAP_CENTER,
          zoom: MAP_ZOOM,
          mapTypeId: 'hybrid',
          tilt: 0,
          streetViewControl: false,
          fullscreenControl: true,
          zoomControl: true,
          rotateControl: true,
          styles: MAP_STYLES,
          gestureHandling: 'greedy',
        });
        mapInstanceRef.current = map;
        geocoderRef.current = new window.google.maps.Geocoder();
        setMapReady(true);
        clearInterval(interval);
      }
    }, 500);
    return () => clearInterval(interval);
  }, []);

  // Handle measure tool lifecycle
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Cleanup any existing listener/polyline
    if (measureClickListenerRef.current) {
      window.google.maps.event.removeListener(measureClickListenerRef.current);
      measureClickListenerRef.current = null;
    }
    if (measurePolylineRef.current) {
      measurePolylineRef.current.setMap(null);
      measurePolylineRef.current = null;
    }
    measurePathRef.current = [];

    if (activeTool !== 'measure') return;

    // Create polyline for measurement
    const polyline = new window.google.maps.Polyline({
      map,
      path: [],
      geodesic: true,
      strokeColor: '#F97316',
      strokeOpacity: 0.9,
      strokeWeight: 3,
    });
    measurePolylineRef.current = polyline;

    // On each click, add a vertex
    measureClickListenerRef.current = map.addListener('click', (e) => {
      const path = [...measurePathRef.current, e.latLng];
      measurePathRef.current = path;
      polyline.setPath(path);
    });

    return () => {
      if (measureClickListenerRef.current) {
        window.google.maps.event.removeListener(measureClickListenerRef.current);
        measureClickListenerRef.current = null;
      }
      if (measurePolylineRef.current) {
        measurePolylineRef.current.setMap(null);
        measurePolylineRef.current = null;
      }
      measurePathRef.current = [];
    };
  }, [activeTool]);

  // Render markers
  useEffect(() => {
    if (!mapReady || !mapInstanceRef.current) return;
    const map = mapInstanceRef.current;

    // Clear old markers
    markersRef.current.forEach(m => m.setMap(null));
    markersRef.current = [];

    const geocoder = geocoderRef.current;

    locations.forEach((loc) => {
      const isSelected = selectedLocation?.id === loc.id;

      const createMarker = (position) => {
        const marker = new window.google.maps.Marker({
          position,
          map,
          title: loc.name,
          icon: {
            url: createMarkerSVG(loc.type, isSelected),
            scaledSize: new window.google.maps.Size(isSelected ? 44 : 36, isSelected ? 52 : 44),
            anchor: new window.google.maps.Point(isSelected ? 22 : 18, isSelected ? 52 : 44),
          },
          zIndex: isSelected ? 1000 : 1,
          animation: isSelected ? window.google.maps.Animation.BOUNCE : null,
        });

        if (isSelected) {
          setTimeout(() => marker.setAnimation(null), 1500);
        }

        marker.addListener('click', () =>
          onPinClick({ ...loc, lat: position.lat, lng: position.lng })
        );
        markersRef.current.push(marker);
      };

      if (loc.lat != null && loc.lng != null) {
        createMarker({ lat: loc.lat, lng: loc.lng });
        return;
      }

      if (geocoder && loc.address) {
        const cached = geocodeCacheRef.current[loc.address];
        if (cached) {
          createMarker(cached);
          return;
        }

        geocoder.geocode({ address: loc.address }, (results, status) => {
          if (!results || status !== 'OK') return;
          const gLoc = results[0].geometry.location;
          const pos = { lat: gLoc.lat(), lng: gLoc.lng() };
          geocodeCacheRef.current[loc.address] = pos;
          createMarker(pos);
        });
      }
    });
  }, [locations, selectedLocation, mapReady, onPinClick]);

  // Pan to selected location
  useEffect(() => {
    if (!selectedLocation || !mapInstanceRef.current) return;

    let target = null;
    if (selectedLocation.lat != null && selectedLocation.lng != null) {
      target = { lat: selectedLocation.lat, lng: selectedLocation.lng };
    } else if (
      selectedLocation.address &&
      geocodeCacheRef.current[selectedLocation.address]
    ) {
      target = geocodeCacheRef.current[selectedLocation.address];
    }

    if (!target) return;

    mapInstanceRef.current.panTo(target);
    if (mapInstanceRef.current.getZoom() < 13) {
      mapInstanceRef.current.setZoom(13);
    }
  }, [selectedLocation]);

  const handleResetView = useCallback(() => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.setCenter(MAP_CENTER);
    mapInstanceRef.current.setZoom(MAP_ZOOM);
    mapInstanceRef.current.setTilt(0);
    mapInstanceRef.current.setHeading(0);
    setIs3D(false);
  }, []);

  const handleClearMeasure = useCallback(() => {
    setActiveTool('none');
  }, []);

  const handleToggle3D = useCallback(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (!is3D) {
      map.setMapTypeId('hybrid');
      // Ensure sufficient zoom level for 3D building perspective.
      const currentZoom = map.getZoom() || MAP_ZOOM;
      if (currentZoom < 17) {
        map.setZoom(17);
      }
      map.setTilt(45);
      setIs3D(true);
    } else {
      map.setTilt(0);
      map.setHeading(0);
      setIs3D(false);
    }
  }, [is3D]);

  // KML pin click: try to match feature name to a location and open panel
  const handleKmlClick = useCallback((name, latLng) => {
    if (!name || !locations?.length) return;
    const matched = locations.find(
      (loc) => loc.name === name || (name && name.includes(loc.name)) || (loc.name && loc.name.includes(name))
    );
    if (matched) onPinClick(matched);
  }, [locations, onPinClick]);

  return (
    <div className="absolute inset-0">
      <div ref={mapRef} className="w-full h-full" />
      {mapReady && (
        <div className="absolute top-3 right-3 flex flex-col gap-2 z-20">
          <button
            type="button"
            onClick={handleResetView}
            className="bg-gwsa-surface/95 border border-gwsa-border rounded-lg p-2 shadow-panel hover:bg-gwsa-surface-hover transition-colors"
            title="Reset view"
          >
            <RotateCcw className="w-4 h-4 text-gwsa-text" />
          </button>
          <button
            type="button"
            onClick={handleToggle3D}
            className={`bg-gwsa-surface/95 border rounded-lg p-2 shadow-panel transition-colors ${
              is3D
                ? 'border-gwsa-accent bg-gwsa-accent/10'
                : 'border-gwsa-border hover:bg-gwsa-surface-hover'
            }`}
            title="Toggle 3D tilt"
          >
            <Box className="w-4 h-4 text-gwsa-text" />
          </button>
          <button
            type="button"
            onClick={() => setActiveTool(activeTool === 'measure' ? 'none' : 'measure')}
            className={`bg-gwsa-surface/95 border rounded-lg p-2 shadow-panel transition-colors ${
              activeTool === 'measure'
                ? 'border-gwsa-accent bg-gwsa-accent/10'
                : 'border-gwsa-border hover:bg-gwsa-surface-hover'
            }`}
            title="Measure distance"
          >
            <Ruler className="w-4 h-4 text-gwsa-text" />
          </button>
          {activeTool === 'measure' && window.google?.maps?.geometry && (
            <div className="mt-1 px-2 py-1 rounded bg-gwsa-surface/95 border border-gwsa-border text-[11px] text-gwsa-text shadow-panel">
              <span>
                {measurePathRef.current.length >= 2
                  ? (() => {
                      const path = measurePathRef.current;
                      const m =
                        window.google.maps.geometry.spherical.computeLength(path);
                      const km = m / 1000;
                      return `${km.toFixed(2)} km`;
                    })()
                  : 'Click on map to start measuring'}
              </span>
              <button
                type="button"
                onClick={handleClearMeasure}
                className="ml-2 text-gwsa-accent hover:text-gwsa-accent-hover"
              >
                Clear
              </button>
            </div>
          )}
        </div>
      )}
      {mapReady && mapInstanceRef.current && (
        <KmlOverlay map={mapInstanceRef.current} onKmlClick={handleKmlClick} />
      )}
      {!mapReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gwsa-bg/80">
          <div className="text-center">
            <div className="w-10 h-10 border-2 border-gwsa-border border-t-gwsa-accent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-gwsa-text-muted">Initializing map...</p>
          </div>
        </div>
      )}
    </div>
  );
}
