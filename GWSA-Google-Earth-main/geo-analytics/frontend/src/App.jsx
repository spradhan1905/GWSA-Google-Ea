/**
 * GWSA GeoAnalytics — App Root
 * Goodwill Industries of San Antonio
 */
import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import TopBar from './components/Layout/TopBar';
import MapContainer from './components/Map/MapContainer';
import SidePanel from './components/Panel/SidePanel';
import ChatDrawer from './components/Chat/ChatDrawer';
import LoadingSpinner from './components/Layout/LoadingSpinner';
import ActionRail from './components/Shell/ActionRail';
import LayersPanel from './components/Layers/LayersPanel';
import ToolsPanel from './components/Tools/ToolsPanel';
import AnalyticsPanel from './components/Analytics/AnalyticsPanel';
import ReportsPanel from './components/Reports/ReportsPanel';
import { MapControlsProvider } from './context/MapControlsContext';
import { fetchLocations } from './services/api';
import { STORE_LOCATIONS, CONSOLIDATED_LOCATION } from './data/stores';
import { FEATURES } from './config/features';

const MOBILE_LAYOUT_QUERY = '(max-width: 639px)';
const DRAWER_DISMISS_DISTANCE = 90;

function getIsMobileLayout() {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_LAYOUT_QUERY).matches;
}

function withConsolidatedLocation(list = []) {
  const normalized = Array.isArray(list) ? list : [];
  const hasConsolidated = normalized.some(
    (loc) => String(loc?.id || '').toUpperCase() === CONSOLIDATED_LOCATION.id,
  );
  if (hasConsolidated) return normalized;
  return [CONSOLIDATED_LOCATION, ...normalized];
}

export default function App({ onBackToLanding }) {
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [isMobileLayout, setIsMobileLayout] = useState(getIsMobileLayout);
  const [activeRailItem, setActiveRailItem] = useState(null);
  const [drawerDragY, setDrawerDragY] = useState(0);
  const [drawerDragging, setDrawerDragging] = useState(false);
  const drawerDragRef = useRef({ active: false, startY: 0, currentY: 0 });
  const railTriggerRef = useRef(null);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const mediaQuery = window.matchMedia(MOBILE_LAYOUT_QUERY);
    const syncMobileLayout = (event) => {
      setIsMobileLayout(event.matches);
      setActiveRailItem(null);
    };

    syncMobileLayout(mediaQuery);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', syncMobileLayout);
      return () => mediaQuery.removeEventListener('change', syncMobileLayout);
    }

    mediaQuery.addListener(syncMobileLayout);
    return () => mediaQuery.removeListener(syncMobileLayout);
  }, []);

  // Load locations from API (fallback to static data)
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchLocations();
        const data = res.data;
        if (Array.isArray(data) && data.length > 0) {
          const mapped = data.map(loc => ({
            id: loc.LocationID,
            name: loc.LocationName,
            type: loc.LocationType,
            // Manager intentionally omitted to avoid storing personal names in the app state
            address: loc.Address || loc.Address1 || null,
            lat: loc.Latitude,
            lng: loc.Longitude,
          }));
          setLocations(withConsolidatedLocation(mapped));
        } else {
          setLocations(withConsolidatedLocation(STORE_LOCATIONS));
        }
      } catch {
        setLocations(withConsolidatedLocation(STORE_LOCATIONS));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handlePinClick = useCallback((location) => {
    setSelectedLocation(location);
    setPanelOpen(true);
  }, []);

  const handleClosePanel = useCallback(() => {
    setPanelOpen(false);
    setTimeout(() => setSelectedLocation(null), 350);
  }, []);

  const handleSearchSelect = useCallback((location) => {
    setSelectedLocation(location);
    setPanelOpen(true);
  }, []);

  const handleListSelect = useCallback((location) => {
    setSelectedLocation(location);
    setPanelOpen(true);
    if (isMobileLayout) {
      setActiveRailItem(null);
    }
  }, [isMobileLayout]);

  const handleRailSelect = useCallback((itemId, trigger) => {
    railTriggerRef.current = trigger;
    setActiveRailItem((current) => current === itemId ? null : itemId);
  }, []);

  const handleCloseRailPanel = useCallback(() => {
    setActiveRailItem(null);
    window.setTimeout(() => railTriggerRef.current?.focus(), 0);
  }, []);

  const filteredLocations = useMemo(() => {
    let list = locations;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(l =>
        l.name.toLowerCase().includes(q) ||
        l.type.toLowerCase().includes(q)
      );
    }
    if (typeFilter !== 'all') {
      list = list.filter(l => l.type === typeFilter);
    }
    return list;
  }, [locations, searchQuery, typeFilter]);

  const handleDrawerPointerDown = useCallback((event) => {
    if (!isMobileLayout) return;

    drawerDragRef.current = {
      active: true,
      startY: event.clientY,
      currentY: event.clientY,
    };
    setDrawerDragging(true);
    setDrawerDragY(0);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }, [isMobileLayout]);

  const handleDrawerPointerMove = useCallback((event) => {
    if (!drawerDragRef.current.active) return;

    drawerDragRef.current.currentY = event.clientY;
    setDrawerDragY(Math.max(0, event.clientY - drawerDragRef.current.startY));
  }, []);

  const finishDrawerDrag = useCallback(() => {
    if (!drawerDragRef.current.active) return;

    const distance = Math.max(
      0,
      drawerDragRef.current.currentY - drawerDragRef.current.startY,
    );
    drawerDragRef.current.active = false;
    setDrawerDragging(false);

    if (distance >= DRAWER_DISMISS_DISTANCE) {
      handleCloseRailPanel();
    }
    setDrawerDragY(0);
  }, [handleCloseRailPanel]);

  const dragHandleProps = isMobileLayout
    ? {
        onPointerDown: handleDrawerPointerDown,
        onPointerMove: handleDrawerPointerMove,
        onPointerUp: finishDrawerDrag,
        onPointerCancel: finishDrawerDrag,
      }
    : undefined;

  const renderRailPanel = () => {
    const panelProps = {
      onClose: handleCloseRailPanel,
      mobile: isMobileLayout,
      dragHandleProps,
    };

    switch (activeRailItem) {
      case 'layers':
        return (
          <LayersPanel
            {...panelProps}
            locations={filteredLocations}
            selectedLocation={selectedLocation}
            onSelectLocation={handleListSelect}
            typeFilter={typeFilter}
            onTypeFilterChange={setTypeFilter}
          />
        );
      case 'tools':
        return <ToolsPanel {...panelProps} />;
      case 'analytics':
        return <AnalyticsPanel {...panelProps} />;
      case 'reports':
        return <ReportsPanel {...panelProps} />;
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gwsa-bg">
        <LoadingSpinner size="lg" text="Loading GWSA GeoAnalytics..." />
      </div>
    );
  }

  return (
    <MapControlsProvider>
      <div className="flex h-screen flex-col overflow-hidden bg-gwsa-bg">
        <TopBar
          locations={locations}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onSearchSelect={handleSearchSelect}
          onChatToggle={() => setChatOpen(!chatOpen)}
          chatOpen={chatOpen}
          aiEnabled={FEATURES.ai}
          onBackToLanding={onBackToLanding}
        />

        <div className="relative flex min-h-0 flex-1 overflow-hidden">
          {!isMobileLayout && (
            <>
              <ActionRail activeItem={activeRailItem} onSelect={handleRailSelect} />
              {activeRailItem && renderRailPanel()}
            </>
          )}

          <main className="relative min-w-0 flex-1 overflow-hidden">
            <MapContainer
              locations={filteredLocations}
              selectedLocation={selectedLocation}
              onPinClick={handlePinClick}
            />

            <SidePanel
              location={selectedLocation}
              open={panelOpen}
              onClose={handleClosePanel}
            />

            {FEATURES.ai && (
              <ChatDrawer
                open={chatOpen}
                onClose={() => setChatOpen(false)}
                storeContext={selectedLocation?.name}
              />
            )}
          </main>

          {isMobileLayout && activeRailItem && (
            <>
              <button
                type="button"
                aria-label="Close navigation panel"
                onClick={handleCloseRailPanel}
                className="absolute inset-0 z-20 bg-slate-950/20 backdrop-blur-[1px] animate-fade-in"
              />
              <div
                className={`absolute inset-x-3 bottom-rail top-16 z-rail-panel ${
                  drawerDragging ? 'transition-none' : 'transition-transform duration-200 ease-out'
                }`}
                style={drawerDragY > 0 ? { transform: `translateY(${drawerDragY}px)` } : undefined}
              >
                {renderRailPanel()}
              </div>
            </>
          )}

          {isMobileLayout && (
            <ActionRail
              activeItem={activeRailItem}
              mobile
              onSelect={handleRailSelect}
            />
          )}
        </div>
      </div>
    </MapControlsProvider>
  );
}
