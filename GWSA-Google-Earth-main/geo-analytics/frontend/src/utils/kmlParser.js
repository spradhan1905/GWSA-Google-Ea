/**
 * GWSA GeoAnalytics — KML Parser Utility
 * Parses KML XML into structured store data.
 */

export function parseKmlText(kmlText) {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(kmlText, 'application/xml');
    const placemarks = doc.querySelectorAll('Placemark');

    return Array.from(placemarks).map((pm, index) => {
      const name = pm.querySelector('name')?.textContent?.trim() || `Location ${index}`;
      const description = pm.querySelector('description')?.textContent?.trim() || '';
      const coordsEl = pm.querySelector('coordinates');
      const styleUrl = pm.querySelector('styleUrl')?.textContent || '';

      let lat = 0, lng = 0;
      if (coordsEl) {
        const coords = coordsEl.textContent.trim().split(',');
        lng = parseFloat(coords[0]) || 0;
        lat = parseFloat(coords[1]) || 0;
      }

      return { name, description, lat, lng, styleUrl };
    }).filter(f => f.lat !== 0 && f.lng !== 0);
  } catch {
    return [];
  }
}
