/**
 * GWSA GeoAnalytics — useKmlData hook
 * Parses KML data for map overlays.
 */
import { useState, useEffect } from 'react';

export default function useKmlData(kmlUrl) {
  const [features, setFeatures] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!kmlUrl) return;
    setLoading(true);
    fetch(kmlUrl)
      .then(res => res.text())
      .then(text => {
        try {
          const parser = new DOMParser();
          const doc = parser.parseFromString(text, 'application/xml');
          const placemarks = doc.querySelectorAll('Placemark');
          const parsed = Array.from(placemarks).map(pm => {
            const name = pm.querySelector('name')?.textContent || '';
            const coords = pm.querySelector('coordinates')?.textContent?.trim() || '';
            const [lng, lat] = coords.split(',').map(Number);
            return { name, lat, lng };
          }).filter(f => f.lat && f.lng);
          setFeatures(parsed);
        } catch {
          setFeatures([]);
        }
      })
      .catch(() => setFeatures([]))
      .finally(() => setLoading(false));
  }, [kmlUrl]);

  return { features, loading };
}
