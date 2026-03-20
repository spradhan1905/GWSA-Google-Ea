/**
 * GWSA GeoAnalytics — useLocationData hook
 * Manages location data fetching and state.
 */
import { useState, useEffect } from 'react';
import { fetchLocations } from '../services/api';
import { STORE_LOCATIONS } from '../data/stores';

export default function useLocationData() {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
        setError('Using offline data');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return { locations, loading, error };
}
