import React, { createContext, useContext, useMemo, useState } from 'react';

const MapControlsContext = createContext(null);

export function MapControlsProvider({ children }) {
  const [activeTool, setActiveTool] = useState('none');
  const [is3D, setIs3D] = useState(false);
  const [mapTypeId, setMapTypeId] = useState('roadmap');
  const [incomeLayerOn, setIncomeLayerOn] = useState(false);
  const [incomeLayerStatus, setIncomeLayerStatus] = useState({
    loading: false,
    error: null,
    ready: false,
    meta: null,
    hasNoData: false,
  });
  const [resetViewRequest, setResetViewRequest] = useState(0);

  const value = useMemo(() => ({
    activeTool,
    setActiveTool,
    is3D,
    setIs3D,
    mapTypeId,
    setMapTypeId,
    incomeLayerOn,
    setIncomeLayerOn,
    incomeLayerStatus,
    setIncomeLayerStatus,
    resetViewRequest,
    requestResetView: () => setResetViewRequest((request) => request + 1),
  }), [
    activeTool,
    is3D,
    mapTypeId,
    incomeLayerOn,
    incomeLayerStatus,
    resetViewRequest,
  ]);

  return (
    <MapControlsContext.Provider value={value}>
      {children}
    </MapControlsContext.Provider>
  );
}

export function useMapControls() {
  const context = useContext(MapControlsContext);
  if (!context) {
    throw new Error('useMapControls must be used within MapControlsProvider');
  }
  return context;
}
