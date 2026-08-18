/**
 * GWSA GeoAnalytics — Map Container
 * Google Maps satellite view centered on San Antonio.
 * Renders location pins with custom markers and optional KML overlay.
 */
import React, { useRef, useEffect, useState, useCallback } from 'react';
import { LOCATION_TYPE_CONFIG, LOCATION_TYPE_FALLBACK } from '../../data/stores';
import { useMapControls } from '../../context/MapControlsContext';
import KmlOverlay from './KmlOverlay';
import MedianIncomeLayer from './MedianIncomeLayer';
import { getIsMobileMap, MOBILE_MAP_QUERY } from '../../utils/mapDevice';

const MAP_CENTER = { lat: 29.4241, lng: -98.4936 };
// Slightly closer default zoom so 3D buildings and roads feel crisper.
const MAP_ZOOM = 12;

// Use Google's default satellite styling for a clean, modern look.
// Leaving this array empty means we don't override Google's visual design.
const MAP_STYLES = [];

function createMarkerSVG(type, isSelected) {
  const cfg = LOCATION_TYPE_CONFIG[type] || LOCATION_TYPE_FALLBACK;
  const color = cfg.color;
  const size = isSelected ? 44 : 36;
  const glow = isSelected ? `<circle cx="${size/2}" cy="${size/2}" r="${size/2}" fill="${color}" opacity="0.25"/>` : '';
  const innerR = Math.max(4, size / 2 - 11);

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size+8}" viewBox="0 0 ${size} ${size+8}">
      ${glow}
      <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="rgba(0,0,0,0.4)"/>
        </filter>
      </defs>
      <circle cx="${size/2}" cy="${size/2}" r="${size/2 - 3}" fill="${color}" filter="url(#shadow)" stroke="white" stroke-width="2"/>
      <circle cx="${size/2}" cy="${size/2}" r="${innerR}" fill="white" opacity="0.92"/>
      <circle cx="${size/2}" cy="${size/2}" r="${innerR * 0.45}" fill="${color}" opacity="0.95"/>
      <polygon points="${size/2 - 5},${size - 3} ${size/2},${size + 5} ${size/2 + 5},${size - 3}" fill="${color}"/>
    </svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function getMarkerIcon(type, isSelected) {
  const cfg = LOCATION_TYPE_CONFIG[type] || LOCATION_TYPE_FALLBACK;
  const marker = cfg.marker;

  if (marker) {
    const scale = isSelected ? 1.18 : 1;
    const width = Math.round(marker.width * scale);
    const height = Math.round(marker.height * scale);

    return {
      url: marker.url,
      scaledSize: new window.google.maps.Size(width, height),
      anchor: new window.google.maps.Point(width / 2, height),
    };
  }

  return {
    url: createMarkerSVG(type, isSelected),
    scaledSize: new window.google.maps.Size(isSelected ? 44 : 36, isSelected ? 52 : 44),
    anchor: new window.google.maps.Point(isSelected ? 22 : 18, isSelected ? 52 : 44),
  };
}

export default function MapContainer({ locations = [], selectedLocation, onPinClick }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const geocoderRef = useRef(null);
  const geocodeCacheRef = useRef({});
  const [mapReady, setMapReady] = useState(false);
  const [isMobileMap, setIsMobileMap] = useState(getIsMobileMap);
  const {
    activeTool,
    is3D,
    setIs3D,
    mapTypeId,
    setMapTypeId,
    incomeLayerOn,
    setIncomeLayerStatus,
    resetViewRequest,
  } = useMapControls();
  const mapWrapRef = useRef(null);
  const measurePolylineRef = useRef(null);
  const measurePathRef = useRef([]);
  const measureClickListenerRef = useRef(null);

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_MAP_QUERY);
    const onChange = () => setIsMobileMap(mq.matches);
    onChange();
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  // Initialize Google Map
  useEffect(() => {
    if (!window.google?.maps || mapInstanceRef.current) return;
    const isMobileMap = getIsMobileMap();

    const map = new window.google.maps.Map(mapRef.current, {
      center: MAP_CENTER,
      zoom: isMobileMap ? 11 : MAP_ZOOM,
      mapTypeId: 'roadmap',
      tilt: 0,
      mapTypeControl: !isMobileMap,
      mapTypeControlOptions: {
        style: window.google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
        position: window.google.maps.ControlPosition.TOP_LEFT,
        mapTypeIds: ['hybrid', 'satellite', 'roadmap'],
      },
      streetViewControl: false,
      fullscreenControl: !isMobileMap,
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
        const isMobileMap = getIsMobileMap();
        const map = new window.google.maps.Map(mapRef.current, {
          center: MAP_CENTER,
          zoom: isMobileMap ? 11 : MAP_ZOOM,
          mapTypeId: 'roadmap',
          tilt: 0,
          streetViewControl: false,
          fullscreenControl: !isMobileMap,
          zoomControl: true,
          rotateControl: true,
          mapTypeControl: !isMobileMap,
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

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!mapReady || !map) return undefined;
    const listener = map.addListener('maptypeid_changed', () => {
      setMapTypeId(map.getMapTypeId() || 'hybrid');
    });
    return () => window.google?.maps?.event?.removeListener(listener);
  }, [mapReady, setMapTypeId]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!mapReady || !map || map.getMapTypeId() === mapTypeId) return;
    map.setMapTypeId(mapTypeId);
  }, [mapReady, mapTypeId]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!mapReady || !map) return;
    if (is3D) {
      if (map.getMapTypeId() !== 'hybrid') {
        map.setMapTypeId('hybrid');
        setMapTypeId('hybrid');
      }
      if ((map.getZoom() || MAP_ZOOM) < 17) map.setZoom(17);
      map.setTilt(45);
    } else {
      map.setTilt(0);
      map.setHeading(0);
    }
  }, [is3D, mapReady, setMapTypeId]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!mapReady || !map) return;
    map.setCenter(MAP_CENTER);
    map.setZoom(isMobileMap ? 11 : MAP_ZOOM);
    map.setTilt(0);
    map.setHeading(0);
    setIs3D(false);
  }, [resetViewRequest, mapReady, isMobileMap, setIs3D]);

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
          icon: getMarkerIcon(loc.type, isSelected),
          zIndex: isSelected ? 1000 : 100,
          animation: isSelected ? window.google.maps.Animation.BOUNCE : null,
          clickable: true,
          optimized: false,
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

  // KML pin click: try to match feature name to a location and open panel
  const handleKmlClick = useCallback((name, latLng) => {
    if (!name || !locations?.length) return;
    const matched = locations.find(
      (loc) => loc.name === name || (name && name.includes(loc.name)) || (loc.name && loc.name.includes(name))
    );
    if (matched) onPinClick(matched);
  }, [locations, onPinClick]);

  return (
    <div ref={mapWrapRef} className="absolute inset-0">
      <div ref={mapRef} className="w-full h-full" />
      {mapReady && (
        <MedianIncomeLayer
          map={mapInstanceRef.current}
          enabled={incomeLayerOn}
          mapPortalRef={mapWrapRef}
          onStatusChange={setIncomeLayerStatus}
        />
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
