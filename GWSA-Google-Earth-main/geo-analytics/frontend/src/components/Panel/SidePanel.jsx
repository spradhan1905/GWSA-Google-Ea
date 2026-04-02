/**
 * GWSA GeoAnalytics — Side Panel
 * Slide-in dashboard panel with financial/operational tabs.
 */
import React, { useState, useEffect, useMemo } from 'react';
import { X, ChevronLeft, TrendingUp, DoorOpen, BarChart3, ExternalLink } from 'lucide-react';
import { LOCATION_TYPE_CONFIG, LOCATION_TYPE_FALLBACK } from '../../data/stores';
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
];

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
  /** Drives API: This Month + Custom → TotalCoreTableFinal; Quarter/YTD/12 Months → RetailStoreMonthlyFinancialSummary. */
  const [financialsPreset, setFinancialsPreset] = useState('This Month');
  const [financials, setFinancials] = useState([]);
  const [doorCount, setDoorCount] = useState([]);
  const [doorCountError, setDoorCountError] = useState(null);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // MTD range (calendar month to date) + This Month preset whenever the user picks a location
  useEffect(() => {
    if (!location?.id) return;
    const end = new Date();
    const start = new Date(end.getFullYear(), end.getMonth(), 1);
    setDateRange({
      start: localDateISO(start),
      end: localDateISO(end),
    });
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
        const [finRes, dcRes, trRes] = await Promise.allSettled([
          fetchFinancials(location.id, dateRange.start, dateRange.end, {
            thisMonth:
              financialsPreset === 'This Month' || financialsPreset === 'Custom',
          }),
          fetchDoorCount(location.id, dateRange.start, dateRange.end),
          fetchTrends(location.id, 12),
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
  }, [location?.id, dateRange.start, dateRange.end, financialsPreset]);

  // Reset tab on new location
  useEffect(() => { setActiveTab('financials'); }, [location?.id]);

  if (!location) return null;
  const typeCfg = LOCATION_TYPE_CONFIG[location.type] || LOCATION_TYPE_FALLBACK;
  const TypeIcon = typeCfg.Icon || LOCATION_TYPE_FALLBACK.Icon;

  const usesTotalCoreDaily =
    financialsPreset === 'This Month' || financialsPreset === 'Custom';

  // Revenue: daily NetRevenue (This Month / Custom) or monthly TotalRevenue (Quarter / YTD / 12 Months)
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
        <MetricSelector tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Date Range */}
        <div className="shrink-0 px-5 py-2">
          <DateRangePicker
            dateRange={dateRange}
            preset={financialsPreset}
            onChange={({ start, end, preset }) => {
              setDateRange({ start, end });
              setFinancialsPreset(preset);
            }}
          />
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
              {activeTab === 'trends' && <TrendsTab data={trends} />}
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

  // Quarter / YTD / 12 Months: RetailStoreMonthlyFinancialSummary (monthly rollups).
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
        Same presets as Financials (This Month, Quarter, YTD, 12 Months).{' '}
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

/** Illustrative 12-month series when API returns no rows (UI preview only). */
function sampleTrendRows() {
  const rows = [];
  const now = new Date();
  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
    const t = 11 - i;
    rows.push({
      PeriodMonth: iso,
      NetIncome: 42000 + t * 1800,
      NetRevenue: 175000 + t * 4200,
      DoorCount: 820 + t * 45,
      ExpenseRatio: 0.125 + t * 0.0012,
    });
  }
  return rows;
}

function TrendsTab({ data }) {
  const [activeMetrics, setActiveMetrics] = useState(['NetIncome', 'NetRevenue', 'DoorCount']);

  const metricOptions = [
    { key: 'NetIncome', label: 'Net Income', color: '#10B981' },
    { key: 'NetRevenue', label: 'Revenue', color: '#3B82F6' },
    { key: 'DoorCount', label: 'Door Count', color: '#06B6D4' },
    { key: 'ExpenseRatio', label: 'Expense Ratio', color: '#F59E0B' },
  ];

  const sampleRows = useMemo(() => sampleTrendRows(), []);
  const hasLive = data.length > 0;
  const sourceRows = hasLive ? data : sampleRows;

  const toggleMetric = (key) => {
    setActiveMetrics(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  };

  const chartData = sourceRows.map((d) => ({
    date: d.PeriodMonth,
    ...Object.fromEntries(activeMetrics.map((k) => [k, d[k]])),
  }));

  const lines = metricOptions
    .filter((m) => activeMetrics.includes(m.key))
    .map((m) => ({ key: m.key, color: m.color, name: m.label }));

  return (
    <div className="space-y-4 pt-2">
      {!hasLive && (
        <p className="text-[11px] text-gwsa-text-muted rounded-lg border border-gwsa-border/80 bg-gwsa-bg-alt/60 px-3 py-2 leading-snug">
          <span className="font-medium text-gwsa-text-secondary">Sample preview</span>
          {' — '}
          Illustrative trend lines. When SQL returns monthly rows for this store, live metrics replace this preview.
        </p>
      )}
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
          title={hasLive ? 'Multi-metric trends' : 'Multi-metric trends (sample)'}
          lines={lines}
        />
      ) : (
        <p className="text-sm text-gwsa-text-muted pt-2">Select at least one metric above.</p>
      )}
    </div>
  );
}
