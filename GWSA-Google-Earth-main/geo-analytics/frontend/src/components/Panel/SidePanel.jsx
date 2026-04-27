/**
 * GWSA GeoAnalytics — Side Panel
 * Slide-in dashboard panel with financial/operational tabs.
 */
import React, { useState, useEffect } from 'react';
import {
  X,
  ChevronLeft,
  TrendingUp,
  DoorOpen,
  BarChart3,
  ExternalLink,
  User,
  Phone,
  Users,
} from 'lucide-react';
import { LOCATION_TYPE_CONFIG, LOCATION_TYPE_FALLBACK } from '../../data/stores';
import { STORE_OPS_INFO_BY_ID } from '../../data/storeOpsInfo';
import MetricCard from './MetricCard';
import TrendChart from './TrendChart';
import DateRangePicker from './DateRangePicker';
import MetricSelector from './MetricSelector';
import LoadingSpinner from '../Layout/LoadingSpinner';
import { fetchFinancials, fetchDoorCount, fetchTrends } from '../../services/api';
import { formatCurrency, formatPercent, formatNumber, getChangeIndicator } from '../../utils/formatters';
import { localDateISO, calendarDaysInclusive, formatDateShort } from '../../utils/dateUtils';

const TABS = [
  { id: 'financials', label: 'Financials', icon: TrendingUp },
  { id: 'doorcount', label: 'Door Count', icon: DoorOpen },
  { id: 'trends', label: 'Trends', icon: BarChart3 },
  { id: 'info', label: 'Info', icon: User },
];
const CONSOLIDATED_ONLY_PRESETS = ['Rolling 3 months', 'YTD', '12 Months'];

function monthSpanInclusive(startIso, endIso) {
  if (!startIso || !endIso) return 12;
  const start = new Date(`${startIso}T12:00:00`);
  const end = new Date(`${endIso}T12:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return 12;
  return ((end.getFullYear() - start.getFullYear()) * 12) + (end.getMonth() - start.getMonth()) + 1;
}

function rangeForPreset(presetLabel) {
  const today = new Date();
  let end = new Date(today);
  let start = new Date(today.getFullYear(), today.getMonth(), 1);
  if (presetLabel === 'YTD') {
    end = new Date(today.getFullYear(), today.getMonth(), 0);
    start = new Date(end.getFullYear(), 0, 1);
  } else if (presetLabel === 'Rolling 3 months') {
    end = new Date(today.getFullYear(), today.getMonth(), 0);
    start = new Date(end.getFullYear(), end.getMonth() - 2, 1);
  } else if (presetLabel === '12 Months') {
    end = new Date(today.getFullYear(), today.getMonth(), 0);
    start = new Date(end.getFullYear(), end.getMonth() - 11, 1);
  }
  return { start: localDateISO(start), end: localDateISO(end) };
}

export default function SidePanel({ location, open, onClose }) {
  const [activeTab, setActiveTab] = useState('financials');
  const [dateRange, setDateRange] = useState(() => {
    const end = new Date();
    const start = new Date(end.getFullYear(), end.getMonth(), 1);
    return {
      start: localDateISO(start),
      end: localDateISO(end),
    };
  });
  /** Drives API: This Month + Custom → TotalCoreTableFinal; Rolling 3 months/YTD/12 Months → RetailStoreMonthlyFinancialSummary. */
  const [financialsPreset, setFinancialsPreset] = useState('This Month');
  const [financials, setFinancials] = useState([]);
  const [doorCount, setDoorCount] = useState([]);
  const [doorCountError, setDoorCountError] = useState(null);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const isConsolidated = String(location?.id || '').toUpperCase() === 'CONSOLIDATED';
  const storeOpsInfo = STORE_OPS_INFO_BY_ID[String(location?.id ?? '')] || null;
  const isInfoEligible = location?.type === 'store' || location?.type === 'outlet';
  const availableTabs = TABS.filter((tab) => {
    if (isConsolidated && tab.id === 'doorcount') return false;
    if (tab.id === 'info' && (!isInfoEligible || !storeOpsInfo)) return false;
    return true;
  });

  // Default range/preset whenever the user picks a location.
  useEffect(() => {
    if (!location?.id) return;
    if (isConsolidated) {
      setDateRange(rangeForPreset('Rolling 3 months'));
      setFinancialsPreset('Rolling 3 months');
      return;
    }
    setDateRange(rangeForPreset('This Month'));
    setFinancialsPreset('This Month');
  }, [location?.id]);

  // Fetch data when location or date changes
  useEffect(() => {
    if (!location?.id || !dateRange.start || !dateRange.end) return;
    setError(null);
    setDoorCountError(null);

    const loadData = async () => {
      setLoading(true);
      try {
        const rangeMonths = Math.min(60, Math.max(1, monthSpanInclusive(dateRange.start, dateRange.end)));
        const trendMonths =
          financialsPreset === 'Rolling 3 months'
            ? 3
            : financialsPreset === '12 Months'
              ? 12
              : financialsPreset === 'YTD'
                ? rangeMonths
                : 12;
        const [finRes, dcRes, trRes] = await Promise.allSettled([
          fetchFinancials(location.id, dateRange.start, dateRange.end, {
            thisMonth:
              !isConsolidated && (financialsPreset === 'This Month' || financialsPreset === 'Custom'),
          }),
          isConsolidated
            ? Promise.resolve({ data: [] })
            : fetchDoorCount(location.id, dateRange.start, dateRange.end),
          fetchTrends(location.id, trendMonths),
        ]);
        if (finRes.status === 'fulfilled') setFinancials(finRes.value.data || []);
        if (dcRes.status === 'fulfilled') {
          const payload = dcRes.value.data;
          setDoorCount(Array.isArray(payload) ? payload : []);
        } else {
          setDoorCount([]);
          const err = dcRes.reason;
          const detail =
            err?.response?.data?.error ??
            (typeof err?.response?.data === 'string' ? err.response.data : null);
          setDoorCountError(
            detail || err?.message || 'Could not load door counts. Check SQL / PeopleCounter.',
          );
        }
        if (trRes.status === 'fulfilled') setTrends(trRes.value.data || []);
      } catch (e) {
        setError('Failed to load data. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [location?.id, dateRange.start, dateRange.end, financialsPreset, isConsolidated]);

  // Reset tab on new location
  useEffect(() => { setActiveTab('financials'); }, [location?.id]);
  useEffect(() => {
    if (availableTabs.some((tab) => tab.id === activeTab)) return;
    setActiveTab('financials');
  }, [activeTab, availableTabs]);

  if (!location) return null;
  const typeCfg = LOCATION_TYPE_CONFIG[location.type] || LOCATION_TYPE_FALLBACK;
  const TypeIcon = typeCfg.Icon || LOCATION_TYPE_FALLBACK.Icon;

  const usesTotalCoreDaily =
    !isConsolidated && (financialsPreset === 'This Month' || financialsPreset === 'Custom');

  // Revenue: daily NetRevenue (This Month / Custom) or monthly TotalRevenue (Rolling 3 months / YTD / 12 Months)
  const totalRevenue = financials.reduce(
    (s, f) => s + (f.TotalRevenue ?? f.NetRevenue ?? 0),
    0,
  );
  const totalOperating = financials.reduce((s, f) => s + (f.OperatingExpenses ?? 0), 0);
  const totalIncome = financials.reduce((s, f) => s + (f.NetIncome || 0), 0);
  const weightedExpenseRatio = totalRevenue > 0 ? totalOperating / totalRevenue : 0;
  const lastTwoFin = financials.slice(-2);
  const incomeChange = lastTwoFin.length === 2
    ? getChangeIndicator(lastTwoFin[1].NetIncome, lastTwoFin[0].NetIncome) : null;

  // Door count KPIs — DonorVisits maps to source column "In" (daily rows; same presets as Financials).
  const doorCalendarDays = calendarDaysInclusive(dateRange.start, dateRange.end);
  const totalVisits = doorCount.reduce((s, d) => s + (d.DonorVisits || 0), 0);
  const avgDaily =
    doorCalendarDays > 0 ? Math.round(totalVisits / doorCalendarDays) : 0;
  const peakDay = doorCount.reduce((max, d) =>
    (d.DonorVisits || 0) > (max.DonorVisits || 0) ? d : max, {});

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
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: `${typeCfg.color}20`, color: typeCfg.color }}>
              <TypeIcon className="w-5 h-5" strokeWidth={1.75} aria-hidden />
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
        <MetricSelector tabs={availableTabs} activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Date Range (hidden for static Info tab) */}
        {activeTab !== 'info' && (
          <div className="shrink-0 px-5 py-2">
            <DateRangePicker
              dateRange={dateRange}
              preset={financialsPreset}
              allowedPresets={isConsolidated ? CONSOLIDATED_ONLY_PRESETS : null}
              showCustom={!isConsolidated}
              onChange={({ start, end, preset }) => {
                setDateRange({ start, end });
                setFinancialsPreset(preset);
              }}
            />
          </div>
        )}

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
                  location={location}
                  data={financials}
                  totalRevenue={totalRevenue}
                  financialsPreset={financialsPreset}
                  usesTotalCoreDaily={usesTotalCoreDaily}
                  totalIncome={totalIncome}
                  totalOperating={totalOperating}
                  weightedExpenseRatio={weightedExpenseRatio}
                  incomeChange={incomeChange}
                />
              )}
              {activeTab === 'doorcount' && (
                <DoorCountTab
                  data={doorCount}
                  totalVisits={totalVisits}
                  avgDaily={avgDaily}
                  peakDay={peakDay}
                  preset={financialsPreset}
                  rangeStart={dateRange.start}
                  rangeEnd={dateRange.end}
                  calendarDays={doorCalendarDays}
                  loadError={doorCountError}
                />
              )}
              {activeTab === 'trends' && (
                <TrendsTab
                  data={trends}
                  preset={financialsPreset}
                  financialsData={financials}
                  doorCountData={doorCount}
                  includeDoorCount={!isConsolidated}
                />
              )}
              {activeTab === 'info' && <StoreInfoTab info={storeOpsInfo} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Tab Content Components ─── */

function FinancialsTab({
  location,
  data,
  totalRevenue,
  financialsPreset,
  usesTotalCoreDaily,
  totalIncome,
  totalOperating,
  weightedExpenseRatio,
  incomeChange,
}) {
  const isRetail = location?.type === 'store';
  const isThisMonth = financialsPreset === 'This Month';

  // This Month / custom range: daily Core Sales revenue from TotalCoreTableFinal.
  if (usesTotalCoreDaily) {
    const revenueLabel = isThisMonth ? 'MTD Revenue' : 'Revenue';
    const revenueSub = isThisMonth
      ? 'Core Sales · calendar month to date'
      : 'Core Sales · selected date range';
    const chartTitle = isThisMonth
      ? 'Daily revenue (MTD)'
      : 'Daily revenue (selected range)';
    return (
      <div className="space-y-4 pt-2">
        <MetricCard
          label={revenueLabel}
          value={formatCurrency(totalRevenue)}
          color="blue"
          subtext={revenueSub}
        />
        {!isRetail && (
          <p className="text-xs text-gwsa-text-muted -mt-2">
            Retail POS totals in sales data. Filter the list to <strong className="font-medium text-gwsa-text-secondary">Retail</strong> for store-level totals.
          </p>
        )}
        {data.length > 0 && (
          <TrendChart
            data={data.map(d => ({
              date: d.SalesDate || d.PeriodMonth,
              value: d.NetRevenue,
            }))}
            title={chartTitle}
            lines={[{ key: 'value', color: '#3B82F6', name: 'Revenue' }]}
            dateAxisGranularity="day"
          />
        )}
      </div>
    );
  }

  // Rolling 3 months / YTD / 12 Months: RetailStoreMonthlyFinancialSummary (monthly rollups).
  return (
    <div className="space-y-4 pt-2">
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Total Revenue" value={formatCurrency(totalRevenue)} color="blue" />
        <MetricCard label="Operating Expenses" value={formatCurrency(totalOperating)} color="cyan" />
        <MetricCard label="Net Income" value={formatCurrency(totalIncome)} change={incomeChange} color="green" />
        <MetricCard label="Expense Ratio" value={formatPercent(weightedExpenseRatio)} color="amber" />
      </div>
      {data.length > 0 && (
        <TrendChart
          data={data.map(d => ({
            date: d.PeriodMonth,
            value: d.NetIncome,
            value2: d.TotalRevenue ?? d.NetRevenue,
          }))}
          title="Net Income vs Total Revenue"
          lines={[
            { key: 'value', color: '#10B981', name: 'Net Income' },
            { key: 'value2', color: '#3B82F6', name: 'Total Revenue' },
          ]}
        />
      )}
    </div>
  );
}

function DoorCountTab({
  data,
  totalVisits,
  avgDaily,
  peakDay,
  preset,
  rangeStart,
  rangeEnd,
  calendarDays,
  loadError,
}) {
  const periodLine = `${preset} · ${formatDateShort(rangeStart)} – ${formatDateShort(rangeEnd)}`;
  const peakDate =
    peakDay.CountDate != null
      ? formatDateShort(
          typeof peakDay.CountDate === 'string'
            ? peakDay.CountDate.slice(0, 10)
            : String(peakDay.CountDate),
        )
      : null;

  const daysWithData = data.length;
  const chartSeries =
    data.length <= 120 ? data : data.slice(-120);
  const chartData = chartSeries.map((d) => ({
    date: d.CountDate,
    value: d.DonorVisits,
  }));

  return (
    <div className="space-y-4 pt-2">
      <p className="text-[11px] text-gwsa-text-muted leading-snug">
        Same presets as Financials (This Month, Rolling 3 months, YTD, 12 Months).{' '}
        <strong className="font-medium text-gwsa-text-secondary">In</strong> counts →{' '}
        <code className="text-[10px] bg-gwsa-bg px-1 rounded">DonorVisits</code>
        . Average = total ÷ {calendarDays} calendar days. Peak = max single-day In.
      </p>

      {loadError ? (
        <div className="rounded-lg border border-gwsa-red/40 bg-gwsa-red/10 px-3 py-2 text-xs text-gwsa-red">
          {loadError}
        </div>
      ) : null}

      {!loadError && data.length === 0 ? (
        <p className="text-sm text-gwsa-text-muted">
          No door count rows for this store and date range. Confirm PeopleCounter data exists and the
          location ID matches <code className="text-[11px] bg-gwsa-bg px-1 rounded">PCounter.LocationID</code>.
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-3">
        <MetricCard
          label="Total visits (In)"
          value={formatNumber(totalVisits)}
          color="blue"
          subtext={periodLine}
        />
        <MetricCard
          label="Daily average"
          value={formatNumber(avgDaily)}
          color="green"
          subtext={`Total ÷ ${calendarDays} calendar days`}
        />
        <MetricCard
          label="Peak day"
          value={formatNumber(peakDay.DonorVisits || 0)}
          subtext={peakDate ? `${peakDate} · highest In` : '—'}
          color="amber"
        />
        <MetricCard
          label="Days with data"
          value={formatNumber(daysWithData)}
          color="cyan"
          subtext={
            daysWithData < calendarDays
              ? `${calendarDays} days in range · gaps have no counter rows`
              : 'One row per day in range'
          }
        />
      </div>

      {!loadError && chartData.length > 0 ? (
        <>
          {data.length > 120 ? (
            <p className="text-[10px] text-gwsa-text-muted -mt-1">
              Showing last 120 days of {data.length} in chart.
            </p>
          ) : null}
          <TrendChart
            data={chartData}
            title="Daily visits (In)"
            lines={[{ key: 'value', color: '#06B6D4', name: 'Visits' }]}
            chartType="bar"
            dateAxisGranularity="day"
          />
        </>
      ) : null}
    </div>
  );
}

function TrendsTab({ data, preset, financialsData, doorCountData, includeDoorCount = true }) {
  const isThisMonth = preset === 'This Month';
  const metricOptions = isThisMonth
    ? [
        { key: 'NetRevenue', label: 'Revenue', color: '#3B82F6' },
        ...(includeDoorCount ? [{ key: 'DoorCount', label: 'Door Count', color: '#06B6D4' }] : []),
      ]
    : [
        { key: 'NetIncome', label: 'Net Income', color: '#10B981' },
        { key: 'NetRevenue', label: 'Revenue', color: '#3B82F6' },
        ...(includeDoorCount ? [{ key: 'DoorCount', label: 'Door Count', color: '#06B6D4' }] : []),
        { key: 'ExpenseRatio', label: 'Expense Ratio', color: '#F59E0B' },
      ];
  const [activeMetrics, setActiveMetrics] = useState(
    isThisMonth
      ? (includeDoorCount ? ['NetRevenue', 'DoorCount'] : ['NetRevenue'])
      : (includeDoorCount ? ['NetIncome', 'NetRevenue', 'DoorCount'] : ['NetIncome', 'NetRevenue']),
  );

  useEffect(() => {
    const allowedKeys = isThisMonth
      ? (includeDoorCount ? ['NetRevenue', 'DoorCount'] : ['NetRevenue'])
      : (includeDoorCount ? ['NetIncome', 'NetRevenue', 'DoorCount', 'ExpenseRatio'] : ['NetIncome', 'NetRevenue', 'ExpenseRatio']);
    setActiveMetrics((prev) => {
      const next = prev.filter((k) => allowedKeys.includes(k));
      if (next.length) return next;
      return [allowedKeys[0]];
    });
  }, [isThisMonth, includeDoorCount]);

  const toggleMetric = (key) => {
    setActiveMetrics(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  };

  const chartData = isThisMonth
    ? (() => {
        // This Month trends should use the same daily revenue rows as Financials.
        const byDate = new Map();
        financialsData.forEach((row) => {
          const dt = row.SalesDate || row.PeriodMonth;
          if (!dt) return;
          const key = String(dt).slice(0, 10);
          const current = byDate.get(key) || { date: key, NetRevenue: 0, DoorCount: 0 };
          current.NetRevenue += Number(row.NetRevenue || row.TotalRevenue || 0);
          byDate.set(key, current);
        });
        if (includeDoorCount) {
          doorCountData.forEach((row) => {
            const dt = row.CountDate;
            if (!dt) return;
            const key = String(dt).slice(0, 10);
            const current = byDate.get(key) || { date: key, NetRevenue: 0, DoorCount: 0 };
            current.DoorCount += Number(row.DonorVisits || 0);
            byDate.set(key, current);
          });
        }
        return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
      })()
    : data.map((d) => ({
        date: d.PeriodMonth,
        ...Object.fromEntries(activeMetrics.map((k) => [k, d[k]])),
      }));

  const lines = metricOptions
    .filter((m) => activeMetrics.includes(m.key))
    .map((m) => ({ key: m.key, color: m.color, name: m.label }));

  return (
    <div className="space-y-4 pt-2">
      <div className="flex flex-wrap gap-1.5">
        {metricOptions.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => toggleMetric(m.key)}
            className={`text-xs px-2.5 py-1 rounded-full font-medium transition-all duration-200 ${
              activeMetrics.includes(m.key)
                ? 'text-white shadow-sm'
                : 'text-gwsa-text-muted bg-gwsa-bg-alt border border-gwsa-border hover:border-gwsa-border-light'
            }`}
            style={activeMetrics.includes(m.key) ? { backgroundColor: m.color } : {}}
          >
            {m.label}
          </button>
        ))}
      </div>
      {lines.length > 0 && chartData.length > 0 ? (
        <TrendChart
          data={chartData}
          title={isThisMonth ? 'Multi-metric trends (daily)' : 'Multi-metric trends'}
          lines={lines}
          dateAxisGranularity={isThisMonth ? 'day' : 'month'}
        />
      ) : (
        <p className="text-sm text-gwsa-text-muted pt-2">
          {lines.length === 0 ? 'Select at least one metric above.' : 'No trend data found for this location.'}
        </p>
      )}
    </div>
  );
}

function StoreInfoTab({ info }) {
  const assistants = (info?.assistantManagers || [])
    .map((name) => String(name || '').trim())
    .filter(Boolean);

  if (!info) {
    return (
      <div className="space-y-4 pt-2">
        <p className="text-sm text-gwsa-text-muted">No staffing information available for this location.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 pt-2">
      <div className="rounded-xl border border-gwsa-border bg-gwsa-bg-alt/45 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-gwsa-text-muted mb-1">
          Director
        </p>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-2xl font-bold leading-tight text-gwsa-text">{info.directorName || '—'}</p>
            <p className="text-xs text-gwsa-text-muted mt-0.5">{info.directorTitle || 'Store Operations'}</p>
          </div>
          {info.directorPhone ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-gwsa-accent/30 bg-gwsa-accent/10 px-2.5 py-1 text-[11px] font-medium text-gwsa-accent">
              <Phone className="w-3 h-3" />
              {info.directorPhone}
            </span>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-3.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gwsa-text-muted mb-1">
            General Manager
          </p>
          <p className="text-2xl font-bold leading-tight text-blue-400">
            {info.generalManager || '—'}
          </p>
        </div>
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gwsa-text-muted mb-1">
            GM Cell
          </p>
          <p className="text-2xl font-bold leading-tight text-emerald-400">
            {info.cell || '—'}
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-gwsa-border bg-gwsa-bg-alt/35 p-4">
        <div className="flex items-center gap-2 mb-2.5">
          <Users className="w-3.5 h-3.5 text-gwsa-accent" />
          <p className="text-[10px] font-semibold uppercase tracking-wider text-gwsa-text-muted">
            Assistant Managers
          </p>
        </div>
        {assistants.length ? (
          <div className="flex flex-wrap gap-2">
            {assistants.map((assistant) => (
              <span
                key={assistant}
                className="inline-flex items-center rounded-full border border-gwsa-border-light bg-gwsa-surface px-2.5 py-1 text-xs text-gwsa-text-secondary"
              >
                {assistant}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gwsa-text-muted">No assistant manager entries.</p>
        )}
      </div>
    </div>
  );
}
