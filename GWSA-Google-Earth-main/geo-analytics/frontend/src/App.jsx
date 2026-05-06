/**
 * GWSA GeoAnalytics — App Root
 * Goodwill Industries of San Antonio
 */
import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import TopBar from './components/Layout/TopBar';
import StoreList from './components/StoreList/StoreList';
import MapContainer from './components/Map/MapContainer';
import SidePanel from './components/Panel/SidePanel';
import ChatDrawer from './components/Chat/ChatDrawer';
import LoadingSpinner from './components/Layout/LoadingSpinner';
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => getIsMobileLayout());
  const [drawerDragY, setDrawerDragY] = useState(0);
  const [drawerDragging, setDrawerDragging] = useState(false);
  const drawerDragRef = useRef({ active: false, startY: 0, currentY: 0 });

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const mediaQuery = window.matchMedia(MOBILE_LAYOUT_QUERY);
    const syncMobileLayout = (event) => {
      setIsMobileLayout(event.matches);
      setSidebarCollapsed(event.matches);
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
      setSidebarCollapsed(true);
    }
  }, [isMobileLayout]);

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
      setSidebarCollapsed(true);
    }
    setDrawerDragY(0);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gwsa-bg">
        <LoadingSpinner size="lg" text="Loading GWSA GeoAnalytics..." />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-gwsa-bg">
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

      <div className="flex-1 flex min-h-0 relative">
        {isMobileLayout && !sidebarCollapsed && (
          <button
            type="button"
            aria-label="Close locations list"
            onClick={() => setSidebarCollapsed(true)}
            className="absolute inset-0 z-30 bg-slate-950/20 backdrop-blur-[1px] animate-fade-in"
          />
        )}
        {!sidebarCollapsed && (
          <div
            className={
              isMobileLayout
                ? `absolute inset-x-3 bottom-3 top-20 z-40 animate-slide-up ${drawerDragging ? 'transition-none' : 'transition-transform duration-200 ease-out'}`
                : 'relative z-10 shrink-0'
            }
            style={isMobileLayout && drawerDragY > 0 ? { transform: `translateY(${drawerDragY}px)` } : undefined}
          >
            <StoreList
              locations={filteredLocations}
              selectedLocation={selectedLocation}
              onSelectLocation={handleListSelect}
              typeFilter={typeFilter}
              onTypeFilterChange={setTypeFilter}
              onCollapse={() => setSidebarCollapsed(true)}
              dragHandleProps={
                isMobileLayout
                  ? {
                      onPointerDown: handleDrawerPointerDown,
                      onPointerMove: handleDrawerPointerMove,
                      onPointerUp: finishDrawerDrag,
                      onPointerCancel: finishDrawerDrag,
                    }
                  : undefined
              }
            />
          </div>
        )}
        <div className="flex-1 relative overflow-hidden min-w-0">
          {sidebarCollapsed && (
            <button
              type="button"
              onClick={() => setSidebarCollapsed(false)}
              className={
                isMobileLayout
                  ? 'absolute bottom-5 left-1/2 z-30 -translate-x-1/2 rounded-full bg-gwsa-accent px-4 py-3 text-sm font-semibold text-white shadow-glow-lg transition-all duration-300 hover:bg-gwsa-accent-hover active:scale-95'
                  : 'absolute top-1/2 left-3 -translate-y-1/2 z-30 bg-gwsa-surface/95 border border-gwsa-border rounded-full px-3 py-2 text-xs font-medium text-gwsa-text shadow-panel transition-all duration-200 hover:bg-gwsa-surface-hover active:scale-95'
              }
            >
              {isMobileLayout ? `Browse ${filteredLocations.length} locations` : 'Show locations'}
            </button>
          )}
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
        </div>
      </div>
    </div>
  );
}
