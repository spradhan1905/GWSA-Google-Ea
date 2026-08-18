/**
 * Texas census tract choropleth — green scale, hover tooltip with metrics.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { fetchTexasTractIncomeLayer, fetchTexasTractIncomeMeta } from '../../services/api';
import { getIsMobileMap } from '../../utils/mapDevice';

/** Green ramp (low → high income), visible on satellite. */
export const INCOME_COLORS = [
  '#edf8e9',
  '#bae4b3',
  '#74c476',
  '#31a354',
  '#006d2c',
  '#00441b',
];

const NO_DATA_FILL = 'rgba(148, 163, 184, 0.55)';
const NO_DATA_STROKE = '#64748b';

const sessionCache = { full: null, metro: null };
const sessionLoadPromise = { full: null, metro: null };

function censusLayerScope() {
  return getIsMobileMap() ? 'metro' : 'full';
}

function formatMoney(n) {
  const v = Number(n);
  if (!Number.isFinite(v) || v <= 0) return 'N/A';
  return `$${v.toLocaleString()}`;
}

function shortTractName(label) {
  if (!label) return 'Census tract';
  return String(label)
    .replace(/^Census Tract\s+/i, 'Tract ')
    .replace(/\s+,\s*Texas$/i, '')
    .trim();
}

function featureProps(feature) {
  const props = {};
  if (!feature?.forEachProperty) return props;
  feature.forEachProperty((val, key) => {
    props[key] = val;
  });
  return props;
}

function incomeColor(income, breaks) {
  if (!breaks?.length || income == null || Number(income) <= 0) {
    return NO_DATA_FILL;
  }
  const v = Number(income);
  for (let i = breaks.length - 1; i >= 1; i -= 1) {
    if (v >= breaks[i]) {
      return INCOME_COLORS[Math.min(i - 1, INCOME_COLORS.length - 1)];
    }
  }
  return INCOME_COLORS[0];
}

async function loadCensusData(scope) {
  if (sessionCache[scope]) return sessionCache[scope];
  if (sessionLoadPromise[scope]) return sessionLoadPromise[scope];
  sessionLoadPromise[scope] = Promise.all([
    fetchTexasTractIncomeMeta(scope),
    fetchTexasTractIncomeLayer(scope),
  ]).then(([metaRes, geoRes]) => {
    const payload = { meta: metaRes.data, geojson: geoRes.data, scope };
    sessionCache[scope] = payload;
    return payload;
  });
  return sessionLoadPromise[scope];
}

function HoverTooltip({ hover }) {
  if (!hover?.props) return null;
  const { props, x, y } = hover;
  const name = shortTractName(props.label);

  return (
    <div
      className="pointer-events-none fixed z-[9999] rounded-md border-2 border-[#2563eb] bg-white px-3 py-2 shadow-lg"
      style={{ left: x + 14, top: y - 12 }}
    >
      <p className="text-[13px] font-semibold text-gray-900 whitespace-nowrap flex items-center gap-2">
        <span className="inline-block w-2.5 h-2.5 rounded-full bg-[#31a354] shrink-0" />
        {name}: {formatMoney(props.median_income)}
      </p>
      <div className="mt-1.5 space-y-0.5 text-[11px] text-gray-700 border-t border-gray-200 pt-1.5">
        <p>
          <span className="text-gray-500">Population:</span>{' '}
          {props.population != null ? Number(props.population).toLocaleString() : 'N/A'}
        </p>
        <p>
          <span className="text-gray-500">Households:</span>{' '}
          {props.households != null ? Number(props.households).toLocaleString() : 'N/A'}
        </p>
        <p>
          <span className="text-gray-500">Poverty rate:</span>{' '}
          {props.poverty_rate_pct != null ? `${props.poverty_rate_pct}%` : 'N/A'}
        </p>
        <p>
          <span className="text-gray-500">Median home value:</span>{' '}
          {formatMoney(props.median_home_value)}
        </p>
      </div>
    </div>
  );
}

export default function MedianIncomeLayer({
  map,
  enabled,
  mapPortalRef,
  onLayerActiveChange,
  onStatusChange,
}) {
  const dataLayerRef = useRef(null);
  const listenersRef = useRef([]);
  const hoveredRef = useRef(null);
  const metaRef = useRef(null);
  const attachGenRef = useRef(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [meta, setMeta] = useState(null);
  const [ready, setReady] = useState(false);
  const [hasNoDataTracts, setHasNoDataTracts] = useState(false);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    onStatusChange?.({
      loading,
      error,
      meta,
      ready,
      hasNoData: hasNoDataTracts,
    });
  }, [loading, error, meta, ready, hasNoDataTracts, onStatusChange]);

  const detachDataLayer = useCallback(() => {
    listenersRef.current.forEach((l) => {
      if (window.google?.maps?.event) {
        window.google.maps.event.removeListener(l);
      }
    });
    listenersRef.current = [];
    hoveredRef.current = null;
    setHover(null);
    if (dataLayerRef.current) {
      dataLayerRef.current.setMap(null);
      dataLayerRef.current = null;
    }
    setReady(false);
    onLayerActiveChange?.(false);
  }, [onLayerActiveChange]);

  useEffect(() => {
    if (!enabled || !map || !window.google?.maps) {
      detachDataLayer();
      return undefined;
    }

    const gen = attachGenRef.current + 1;
    attachGenRef.current = gen;
    let cancelled = false;

    const attach = async () => {
      setLoading(true);
      setError(null);
      const scope = censusLayerScope();
      const touchMode = scope === 'metro';
      try {
        const { meta: metaPayload, geojson } = await loadCensusData(scope);
        if (cancelled || attachGenRef.current !== gen) return;

        metaRef.current = metaPayload;
        setMeta(metaPayload);

        const features = geojson.features || [];
        if (!features.length) {
          throw new Error('No census tracts in this area');
        }

        const anyNoData = features.some(
          (f) => !f.properties?.median_income || f.properties.median_income <= 0,
        );
        setHasNoDataTracts(anyNoData);

        detachDataLayer();
        if (cancelled || attachGenRef.current !== gen) return;

        const layer = new window.google.maps.Data({ map });
        layer.addGeoJson(geojson);
        dataLayerRef.current = layer;
        onLayerActiveChange?.(true);

        const breaks = metaPayload?.income_breaks || [];
        layer.setStyle((feature) => {
          const income = Number(feature.getProperty('median_income'));
          const hasData = Number.isFinite(income) && income > 0;
          return {
            fillColor: incomeColor(income, breaks),
            fillOpacity: hasData ? 0.78 : 0.55,
            strokeColor: hasData ? '#166534' : NO_DATA_STROKE,
            strokeWeight: touchMode ? 1 : 1.2,
            strokeOpacity: 0.9,
            clickable: true,
            zIndex: 10,
          };
        });

        const highlight = (feature) => {
          layer.overrideStyle(feature, {
            strokeWeight: 3,
            strokeColor: '#2563eb',
            strokeOpacity: 1,
            fillOpacity: 0.92,
          });
        };

        const unhighlight = (feature) => {
          if (feature) layer.revertStyle(feature);
        };

        const showAtEvent = (e) => {
          const dom = e.domEvent;
          if (!dom) return;
          const props = featureProps(e.feature);
          const x = dom.clientX ?? dom.touches?.[0]?.clientX ?? window.innerWidth / 2;
          const y = dom.clientY ?? dom.touches?.[0]?.clientY ?? window.innerHeight / 2;
          setHover({ props, x, y });
        };

        if (touchMode) {
          listenersRef.current.push(
            layer.addListener('click', (e) => {
              if (hoveredRef.current && hoveredRef.current !== e.feature) {
                unhighlight(hoveredRef.current);
              }
              if (hoveredRef.current === e.feature) {
                unhighlight(e.feature);
                hoveredRef.current = null;
                setHover(null);
                return;
              }
              hoveredRef.current = e.feature;
              highlight(e.feature);
              showAtEvent(e);
            }),
          );
        } else {
          listenersRef.current.push(
            layer.addListener('mouseover', (e) => {
              if (hoveredRef.current && hoveredRef.current !== e.feature) {
                unhighlight(hoveredRef.current);
              }
              hoveredRef.current = e.feature;
              highlight(e.feature);
              map.setOptions({ draggableCursor: 'pointer' });
              showAtEvent(e);
            }),
            layer.addListener('mousemove', (e) => {
              if (hoveredRef.current === e.feature) showAtEvent(e);
            }),
            layer.addListener('mouseout', (e) => {
              unhighlight(e.feature);
              if (hoveredRef.current === e.feature) hoveredRef.current = null;
              setHover(null);
              map.setOptions({ draggableCursor: null });
            }),
          );
        }

        setReady(true);
      } catch (err) {
        if (!cancelled && attachGenRef.current === gen) {
          const msg =
            err.response?.data?.error ||
            err.response?.data?.hint ||
            err.message ||
            'Failed to load income layer';
          setError(typeof msg === 'string' ? msg : 'Failed to load income layer');
        }
      } finally {
        if (!cancelled && attachGenRef.current === gen) {
          setLoading(false);
        }
      }
    };

    attach();
    return () => {
      cancelled = true;
      detachDataLayer();
      if (map?.setOptions) map.setOptions({ draggableCursor: null });
    };
  }, [enabled, map, detachDataLayer, onLayerActiveChange]);

  const portalTarget = mapPortalRef?.current;

  return (
    <>
      {portalTarget && createPortal(
        <HoverTooltip hover={hover} />,
        portalTarget,
      )}
    </>
  );
}
