/**
 * GWSA GeoAnalytics — Side Panel
 * Slide-in dashboard panel with financial/operational tabs.
 */
import React, { useState, useEffect, useRef } from 'react';
import { X, ChevronLeft, TrendingUp, DoorOpen, BarChart3, MapPin, ExternalLink } from 'lucide-react';
import { LOCATION_TYPE_CONFIG } from '../../data/stores';
import MetricCard from './MetricCard';
import TrendChart from './TrendChart';
import DateRangePicker from './DateRangePicker';
import MetricSelector from './MetricSelector';
import LoadingSpinner from '../Layout/LoadingSpinner';
import { fetchFinancials, fetchDoorCount, fetchTrends, fetchDonorAddresses } from '../../services/api';
import { formatCurrency, formatPercent, formatNumber, getChangeIndicator } from '../../utils/formatters';

const TABS = [
  { id: 'financials', label: 'Financials', icon: TrendingUp },
  { id: 'doorcount', label: 'Door Count', icon: DoorOpen },
  { id: 'trends', label: 'Trends', icon: BarChart3 },
  { id: 'donormap', label: 'Donor Map', icon: MapPin },
];

export default function SidePanel({ location, open, onClose }) {
  const [activeTab, setActiveTab] = useState('financials');
  const [dateRange, setDateRange] = useState({ start: null, end: null });
  const [financials, setFinancials] = useState([]);
  const [doorCount, setDoorCount] = useState([]);
  const [trends, setTrends] = useState([]);
  const [donorAddresses, setDonorAddresses] = useState([]);
  const [donorMapLoading, setDonorMapLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Initialize date range (last 12 months)
  useEffect(() => {
    const end = new Date();
    const start = new Date();
    start.setMonth(start.getMonth() - 12);
    start.setDate(1);
    setDateRange({
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    });
  }, []);

  // Fetch data when location or date changes
  useEffect(() => {
    if (!location?.id || !dateRange.start || !dateRange.end) return;
    setError(null);

    const loadData = async () => {
      setLoading(true);
      try {
        const [finRes, dcRes, trRes] = await Promise.allSettled([
          fetchFinancials(location.id, dateRange.start, dateRange.end),
          fetchDoorCount(location.id, dateRange.start, dateRange.end),
          fetchTrends(location.id, 12),
        ]);
        if (finRes.status === 'fulfilled') setFinancials(finRes.value.data || []);
        if (dcRes.status === 'fulfilled') setDoorCount(dcRes.value.data || []);
        if (trRes.status === 'fulfilled') setTrends(trRes.value.data || []);
      } catch (e) {
        setError('Failed to load data. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [location?.id, dateRange.start, dateRange.end]);

  // Reset tab on new location
  useEffect(() => { setActiveTab('financials'); }, [location?.id]);

  // Fetch donor addresses when Donor Map tab is active
  useEffect(() => {
    if (activeTab !== 'donormap' || !location?.id) return;
    setDonorMapLoading(true);
    fetchDonorAddresses(location.id)
      .then(res => setDonorAddresses(Array.isArray(res.data) ? res.data : []))
      .catch(() => setDonorAddresses([]))
      .finally(() => setDonorMapLoading(false));
  }, [activeTab, location?.id]);

  if (!location) return null;
  const typeCfg = LOCATION_TYPE_CONFIG[location.type] || {};

  // Compute KPIs from financials data
  const totalRevenue = financials.reduce((s, f) => s + (f.NetRevenue || 0), 0);
  const totalIncome = financials.reduce((s, f) => s + (f.NetIncome || 0), 0);
  const avgExpense = financials.length > 0
    ? financials.reduce((s, f) => s + (f.ExpenseRatio || 0), 0) / financials.length : 0;
  const totalDonated = financials.reduce((s, f) => s + (f.DonatedGoodsRev || 0), 0);
  const totalRetail = financials.reduce((s, f) => s + (f.RetailRevenue || 0), 0);

  // Door count KPIs
  const totalVisits = doorCount.reduce((s, d) => s + (d.DonorVisits || 0), 0);
  const avgDaily = doorCount.length > 0 ? Math.round(totalVisits / doorCount.length) : 0;
  const peakDay = doorCount.reduce((max, d) => d.DonorVisits > (max.DonorVisits || 0) ? d : max, {});

  // MoM change for income
  const lastTwo = financials.slice(-2);
  const incomeChange = lastTwo.length === 2
    ? getChangeIndicator(lastTwo[1].NetIncome, lastTwo[0].NetIncome) : null;

  // YTD Net Income (current calendar year)
  const currentYear = new Date().getFullYear();
  const ytdNetIncome = financials
    .filter((f) => f.PeriodMonth && f.PeriodMonth.startsWith(String(currentYear)))
    .reduce((s, f) => s + (f.NetIncome || 0), 0);

  return (
    <div className={`absolute top-0 right-0 h-full w-full sm:w-[440px] z-40 transition-transform duration-350 ease-[cubic-bezier(0.16,1,0.3,1)] ${
      open ? 'translate-x-0' : 'translate-x-full'
    }`}>
      <div className="h-full bg-gwsa-surface/95 backdrop-blur-xl border-l border-gwsa-border shadow-panel flex flex-col overflow-hidden">

        {/* Header */}
        <div className="shrink-0 px-5 pt-4 pb-3 border-b border-gwsa-border">
          <div className="flex items-start justify-between mb-2">
            <button onClick={onClose} className="p-1 -ml-1 rounded-lg hover:bg-gwsa-surface-hover transition-colors">
              <ChevronLeft className="w-5 h-5 text-gwsa-text-muted" />
            </button>
            <button onClick={onClose} className="p-1 rounded-lg hover:bg-gwsa-surface-hover transition-colors">
              <X className="w-4 h-4 text-gwsa-text-muted" />
            </button>
          </div>

          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
              style={{ backgroundColor: `${typeCfg.color}20`, color: typeCfg.color }}>
              {typeCfg.icon}
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-base font-bold text-gwsa-text truncate">{location.name}</h2>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="inline-flex items-center text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full"
                  style={{ backgroundColor: `${typeCfg.color}20`, color: typeCfg.color }}>
                  {typeCfg.label}
                </span>
              </div>
            </div>
            {(location.lat != null && location.lng != null) || location.address ? (
              <a
                href={
                  location.lat != null && location.lng != null
                    ? `https://www.waze.com/ul?ll=${location.lat},${location.lng}&navigate=yes`
                    : `https://www.waze.com/ul?q=${encodeURIComponent(location.address)}&navigate=yes`
                }
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-gwsa-accent/20 text-gwsa-accent hover:bg-gwsa-accent/30 transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Get Directions
              </a>
            ) : null}
          </div>
        </div>

        {/* Tabs */}
        <MetricSelector tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Date Range */}
        <div className="shrink-0 px-5 py-2">
          <DateRangePicker dateRange={dateRange} onChange={setDateRange} />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 pb-5">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <LoadingSpinner text="Loading data..." />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-40">
              <p className="text-sm text-gwsa-red">{error}</p>
            </div>
          ) : (
            <>
              {activeTab === 'financials' && (
                <FinancialsTab
                  data={financials} totalRevenue={totalRevenue} totalIncome={totalIncome}
                  avgExpense={avgExpense} totalDonated={totalDonated} totalRetail={totalRetail}
                  incomeChange={incomeChange} ytdNetIncome={ytdNetIncome}
                />
              )}
              {activeTab === 'doorcount' && (
                <DoorCountTab data={doorCount} totalVisits={totalVisits} avgDaily={avgDaily} peakDay={peakDay} />
              )}
              {activeTab === 'trends' && <TrendsTab data={trends} />}
              {activeTab === 'donormap' && (
                <DonorMapTab location={location} donorAddresses={donorAddresses} loading={donorMapLoading} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Tab Content Components ─── */

function FinancialsTab({ data, totalRevenue, totalIncome, avgExpense, totalDonated, totalRetail, incomeChange, ytdNetIncome }) {
  return (
    <div className="space-y-4 pt-2">
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Net Revenue" value={formatCurrency(totalRevenue)} color="blue" />
        <MetricCard label="Net Income" value={formatCurrency(totalIncome)} change={incomeChange} color="green" />
        <MetricCard label="Expense Ratio" value={formatPercent(avgExpense)} color="amber" />
        <MetricCard label="Donated Goods" value={formatCurrency(totalDonated)} color="cyan" />
        <MetricCard label="Retail Revenue" value={formatCurrency(totalRetail)} color="purple" />
        <MetricCard label="YTD Net Income" value={formatCurrency(ytdNetIncome ?? 0)} color="green" />
      </div>
      {data.length > 0 && (
        <TrendChart
          data={data.map(d => ({
            date: d.PeriodMonth,
            value: d.NetIncome,
            value2: d.NetRevenue,
          }))}
          title="Net Income vs Revenue"
          lines={[
            { key: 'value', color: '#10B981', name: 'Net Income' },
            { key: 'value2', color: '#3B82F6', name: 'Revenue' },
          ]}
        />
      )}
    </div>
  );
}

function DoorCountTab({ data, totalVisits, avgDaily, peakDay }) {
  return (
    <div className="space-y-4 pt-2">
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Total Visits" value={formatNumber(totalVisits)} color="blue" />
        <MetricCard label="Daily Average" value={formatNumber(avgDaily)} color="green" />
        <MetricCard label="Peak Day" value={formatNumber(peakDay.DonorVisits || 0)} subtext={peakDay.CountDate} color="amber" />
        <MetricCard label="Data Points" value={formatNumber(data.length)} color="cyan" />
      </div>
      {data.length > 0 && (
        <TrendChart
          data={data.slice(-60).map(d => ({ date: d.CountDate, value: d.DonorVisits }))}
          title="Daily Donor Visits"
          lines={[{ key: 'value', color: '#06B6D4', name: 'Visits' }]}
          chartType="bar"
        />
      )}
    </div>
  );
}

function DonorMapTab({ location, donorAddresses, loading }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);

  useEffect(() => {
    if (!location?.lat || !location?.lng || !window.google?.maps || !mapRef.current) return;

    const center = { lat: location.lat, lng: location.lng };
    const map = new window.google.maps.Map(mapRef.current, {
      center,
      zoom: 13,
      mapTypeId: 'hybrid',
      disableDefaultUI: false,
      zoomControl: true,
      mapTypeControl: true,
      fullscreenControl: false,
      streetViewControl: false,
    });
    mapInstanceRef.current = map;

    // Store marker (larger, distinct)
    const storeMarker = new window.google.maps.Marker({
      position: center,
      map,
      title: location.name,
      icon: {
        path: window.google.maps.SymbolPath.CIRCLE,
        scale: 12,
        fillColor: '#E94560',
        fillOpacity: 1,
        strokeColor: '#fff',
        strokeWeight: 2,
      },
    });
    markersRef.current.push(storeMarker);

    // Donor pins
    donorAddresses.forEach((d) => {
      if (d.Latitude == null || d.Longitude == null) return;
      const m = new window.google.maps.Marker({
        position: { lat: Number(d.Latitude), lng: Number(d.Longitude) },
        map,
        title: d.Address1 || 'Donor',
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 6,
          fillColor: '#00b4d8',
          fillOpacity: 0.8,
          strokeColor: '#fff',
          strokeWeight: 1,
        },
      });
      markersRef.current.push(m);
    });

    // Fit bounds if we have donor points
    if (donorAddresses.length > 0) {
      const bounds = new window.google.maps.LatLngBounds();
      bounds.extend(center);
      donorAddresses.forEach((d) => {
        if (d.Latitude != null && d.Longitude != null)
          bounds.extend({ lat: Number(d.Latitude), lng: Number(d.Longitude) });
      });
      map.fitBounds(bounds, 40);
    }

    return () => {
      markersRef.current.forEach((m) => m.setMap(null));
      markersRef.current = [];
      mapInstanceRef.current = null;
    };
  }, [location?.id, location?.lat, location?.lng, location?.name, donorAddresses]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 pt-2">
        <LoadingSpinner text="Loading donor map..." />
      </div>
    );
  }
  if (!donorAddresses.length) {
    return (
      <div className="pt-2">
        <p className="text-sm text-gwsa-text-muted">
          No donor address data for this location. Donor catchment layers appear here when available.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-2 pt-2">
      <p className="text-xs text-gwsa-text-muted">
        Store (red) and donor addresses (blue) in catchment area.
      </p>
      <div ref={mapRef} className="w-full h-64 rounded-xl overflow-hidden border border-gwsa-border bg-gwsa-bg" />
    </div>
  );
}

function TrendsTab({ data }) {
  const [activeMetrics, setActiveMetrics] = useState(['NetIncome', 'DoorCount']);

  const metricOptions = [
    { key: 'NetIncome', label: 'Net Income', color: '#10B981' },
    { key: 'NetRevenue', label: 'Revenue', color: '#3B82F6' },
    { key: 'DoorCount', label: 'Door Count', color: '#06B6D4' },
    { key: 'ExpenseRatio', label: 'Expense Ratio', color: '#F59E0B' },
    { key: 'DonatedGoodsRev', label: 'Donated Goods', color: '#8B5CF6' },
  ];

  const toggleMetric = (key) => {
    setActiveMetrics(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  };

  return (
    <div className="space-y-4 pt-2">
      <div className="flex flex-wrap gap-1.5">
        {metricOptions.map(m => (
          <button key={m.key} onClick={() => toggleMetric(m.key)}
            className={`text-xs px-2.5 py-1 rounded-full font-medium transition-all duration-200 ${
              activeMetrics.includes(m.key)
                ? 'text-white shadow-sm' : 'text-gwsa-text-muted bg-gwsa-bg-alt border border-gwsa-border hover:border-gwsa-border-light'
            }`}
            style={activeMetrics.includes(m.key) ? { backgroundColor: m.color } : {}}>
            {m.label}
          </button>
        ))}
      </div>
      {data.length > 0 && (
        <TrendChart
          data={data.map(d => ({
            date: d.PeriodMonth,
            ...Object.fromEntries(activeMetrics.map(k => [k, d[k]]))
          }))}
          title="Multi-Metric Trends"
          lines={metricOptions.filter(m => activeMetrics.includes(m.key)).map(m => ({
            key: m.key, color: m.color, name: m.label,
          }))}
        />
      )}
    </div>
  );
}
