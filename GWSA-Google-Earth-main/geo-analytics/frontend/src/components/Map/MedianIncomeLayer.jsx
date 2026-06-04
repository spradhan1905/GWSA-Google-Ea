/**
 * Texas census tract choropleth — green scale, hover tooltip with metrics.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Layers, Loader2 } from 'lucide-react';
import { fetchTexasTractIncomeLayer, fetchTexasTractIncomeMeta } from '../../services/api';

/** Green ramp (low → high income), visible on satellite. */
const INCOME_COLORS = [
  '#edf8e9',
  '#bae4b3',
  '#74c476',
  '#31a354',
  '#006d2c',
  '#00441b',
];

const NO_DATA_FILL = 'rgba(148, 163, 184, 0.55)';
const NO_DATA_STROKE = '#64748b';

let sessionCache = null;
let sessionLoadPromise = null;

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

async function loadCensusData() {
  if (sessionCache) return sessionCache;
  if (sessionLoadPromise) return sessionLoadPromise;
  sessionLoadPromise = Promise.all([
    fetchTexasTractIncomeMeta(),
    fetchTexasTractIncomeLayer(),
  ]).then(([metaRes, geoRes]) => {
    sessionCache = { meta: metaRes.data, geojson: geoRes.data };
    return sessionCache;
  });
  return sessionLoadPromise;
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

function MapLegend({ meta, hasNoData }) {
  const breaks = meta?.income_breaks || [];
  if (breaks.length < 2) return null;

  const segments = [];
  for (let i = 1; i < breaks.length; i += 1) {
    segments.push({
      color: INCOME_COLORS[Math.min(i - 1, INCOME_COLORS.length - 1)],
      low: breaks[i],
      high: breaks[i + 1] ?? breaks[breaks.length - 1],
    });
  }

  return (
    <div className="absolute bottom-20 right-3 z-30 w-[200px] rounded-lg border border-gray-300 bg-white px-3 py-2.5 shadow-lg pointer-events-none">
      <p className="text-xs font-bold text-gray-900 mb-0.5">Median household income</p>
      <p className="text-[10px] text-gray-600 mb-2">Darker green = higher · Hover a tract</p>
      <div className="space-y-1">
        {segments.map((seg, idx) => (
          <div key={idx} className="flex items-center gap-2 text-[10px] text-gray-800">
            <span
              className="w-5 h-3 rounded-sm border border-gray-400 shrink-0"
              style={{ backgroundColor: seg.color }}
            />
            <span className="tabular-nums font-medium">
              {formatMoney(seg.low)}
              {idx < segments.length - 1 ? ` – ${formatMoney(seg.high)}` : '+'}
            </span>
          </div>
        ))}
      </div>
      {hasNoData && (
        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-200 text-[10px] text-gray-700">
          <span
            className="w-5 h-3 rounded-sm border border-gray-500 shrink-0"
            style={{ backgroundColor: NO_DATA_FILL }}
          />
          <span>No ACS estimate</span>
        </div>
      )}
    </div>
  );
}

export default function MedianIncomeLayer({
  map,
  enabled,
  onEnabledChange,
  mapPortalRef,
  onLayerActiveChange,
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
      try {
        const { meta: metaPayload, geojson } = await loadCensusData();
        if (cancelled || attachGenRef.current !== gen) return;

        metaRef.current = metaPayload;
        setMeta(metaPayload);

        const anyNoData = (geojson.features || []).some(
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
            strokeWeight: 1.2,
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

        const showHover = (e) => {
          const dom = e.domEvent;
          if (!dom) return;
          const props = featureProps(e.feature);
          setHover({ props, x: dom.clientX, y: dom.clientY });
        };

        listenersRef.current.push(
          layer.addListener('mouseover', (e) => {
            if (hoveredRef.current && hoveredRef.current !== e.feature) {
              unhighlight(hoveredRef.current);
            }
            hoveredRef.current = e.feature;
            highlight(e.feature);
            map.setOptions({ draggableCursor: 'pointer' });
            showHover(e);
          }),
          layer.addListener('mousemove', (e) => {
            if (hoveredRef.current === e.feature) showHover(e);
          }),
          layer.addListener('mouseout', (e) => {
            unhighlight(e.feature);
            if (hoveredRef.current === e.feature) hoveredRef.current = null;
            setHover(null);
            map.setOptions({ draggableCursor: null });
          }),
        );

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
      <button
        type="button"
        onClick={() => onEnabledChange?.(!enabled)}
        className={`bg-white border rounded-lg p-2 shadow-md transition-all hover:bg-gray-50 active:scale-95 ${
          enabled ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-300'
        }`}
        title="Median income by census tract — hover for details"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 text-gray-800 animate-spin" />
        ) : (
          <Layers className="w-4 h-4 text-gray-800" />
        )}
      </button>

      {enabled && error && (
        <div className="max-w-[180px] px-2 py-1 rounded-md bg-white border border-red-400 text-[10px] text-red-800 shadow-md">
          {error}
        </div>
      )}

      {portalTarget && createPortal(
        <>
          <HoverTooltip hover={hover} />
          {enabled && ready && (
            <MapLegend meta={meta} hasNoData={hasNoDataTracts} />
          )}
        </>,
        portalTarget,
      )}
    </>
  );
}
