/**
 * GWSA GeoAnalytics — App Root
 * Goodwill Industries of San Antonio
 */
import React, { useState, useCallback, useEffect, useMemo } from 'react';
import TopBar from './components/Layout/TopBar';
import StoreList from './components/StoreList/StoreList';
import MapContainer from './components/Map/MapContainer';
import SidePanel from './components/Panel/SidePanel';
import ChatDrawer from './components/Chat/ChatDrawer';
import LoadingSpinner from './components/Layout/LoadingSpinner';
import { fetchLocations } from './services/api';
import { STORE_LOCATIONS } from './data/stores';

export default function App({ onBackToLanding }) {
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
   const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Load locations from API (fallback to static data)
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchLocations();
        const data = res.data;
        if (Array.isArray(data) && data.length > 0) {
          setLocations(data.map(loc => ({
            id: loc.LocationID,
            name: loc.LocationName,
            type: loc.LocationType,
            // Manager intentionally omitted to avoid storing personal names in the app state
            address: loc.Address || loc.Address1 || null,
            lat: loc.Latitude,
            lng: loc.Longitude,
          })));
        } else {
          setLocations(STORE_LOCATIONS);
        }
      } catch {
        setLocations(STORE_LOCATIONS);
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
        onBackToLanding={onBackToLanding}
      />

      <div className="flex-1 flex min-h-0">
        {!sidebarCollapsed && (
          <StoreList
            locations={filteredLocations}
            selectedLocation={selectedLocation}
            onSelectLocation={handleListSelect}
            typeFilter={typeFilter}
            onTypeFilterChange={setTypeFilter}
            onCollapse={() => setSidebarCollapsed(true)}
          />
        )}
        <div className="flex-1 relative overflow-hidden min-w-0">
          {sidebarCollapsed && (
            <button
              type="button"
              onClick={() => setSidebarCollapsed(false)}
              className="absolute top-1/2 left-3 -translate-y-1/2 z-30 bg-gwsa-surface/95 border border-gwsa-border rounded-full px-3 py-2 text-xs font-medium text-gwsa-text shadow-panel hover:bg-gwsa-surface-hover"
            >
              Show locations
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

          <ChatDrawer
            open={chatOpen}
            onClose={() => setChatOpen(false)}
            storeContext={selectedLocation?.name}
          />
        </div>
      </div>
    </div>
  );
}
