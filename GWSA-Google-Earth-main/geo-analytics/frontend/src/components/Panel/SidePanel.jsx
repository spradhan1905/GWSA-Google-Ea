/**
 * GWSA GeoAnalytics — Side Panel
 * Slide-in dashboard panel with financial/operational tabs.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X,
  ChevronLeft,
  TrendingUp,
  BarChart3,
  ExternalLink,
  User,
  Phone,
  Users,
  Gift,
  GripVertical,
  LayoutGrid,
} from 'lucide-react';
import { LOCATION_TYPE_CONFIG, LOCATION_TYPE_FALLBACK } from '../../data/stores';
import { STORE_OPS_INFO_BY_ID } from '../../data/storeOpsInfo';
import MetricCard from './MetricCard';
import TrendChart from './TrendChart';
import DateRangePicker from './DateRangePicker';
import MetricSelector from './MetricSelector';
import LoadingSpinner from '../Layout/LoadingSpinner';
import {
  fetchFinancials,
  fetchDoorCount,
  fetchTrends,
  fetchBudgetVsActual,
  fetchDonations,
  fetchKeyMetrics,
} from '../../services/api';
import { formatCurrency, formatPercent, formatNumber, getChangeIndicator } from '../../utils/formatters';
import { localDateISO, calendarDaysInclusive, formatDateShort, toMonthKey } from '../../utils/dateUtils';
import { FEATURES } from '../../config/features';

const TABS = [
  { id: 'financials', label: 'Financials', icon: TrendingUp },
  { id: 'keymetrics', label: 'Key Metrics', icon: LayoutGrid },
  { id: 'donor-door', label: 'Donor / Door', icon: Gift },
  { id: 'trends', label: 'Trends', icon: BarChart3 },
  { id: 'info', label: 'Info', icon: User },
];
const KPI_TAB_IDS = new Set(['financials', 'keymetrics', 'donor-door', 'trends']);
const CONSOLIDATED_ONLY_PRESETS = ['Rolling 3 months', 'YTD', '12 Months'];

// Desktop panel resize (drag the left-edge handle to stretch the panel width).
const DEFAULT_PANEL_WIDTH = 440;
const MIN_PANEL_WIDTH = 360;
const DESKTOP_MEDIA_QUERY = '(min-width: 640px)';

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
  const [budgetVsActual, setBudgetVsActual] = useState([]);
  const [doorCount, setDoorCount] = useState([]);
  const [doorCountError, setDoorCountError] = useState(null);
  const [donations, setDonations] = useState([]);
  const [donationsError, setDonationsError] = useState(null);
  const [keyMetrics, setKeyMetrics] = useState(null);
  const [keyMetricsError, setKeyMetricsError] = useState(null);
  const [trends, setTrends] = useState([]);
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(DESKTOP_MEDIA_QUERY).matches,
  );
  const [panelWidth, setPanelWidth] = useState(DEFAULT_PANEL_WIDTH);
  const resizeRef = useRef({ active: false, startX: 0, startWidth: DEFAULT_PANEL_WIDTH });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const isConsolidated = String(location?.id || '').toUpperCase() === 'CONSOLIDATED';
  const storeOpsInfo = STORE_OPS_INFO_BY_ID[String(location?.id ?? '')] || null;
  const isInfoEligible = location?.type === 'store' || location?.type === 'outlet';
  const isKeyMetricsEligible = isInfoEligible;
  const availableTabs = TABS.filter((tab) => {
    if (!FEATURES.kpis && KPI_TAB_IDS.has(tab.id)) return false;
    if (tab.id === 'keymetrics' && !isKeyMetricsEligible) return false;
    if (tab.id === 'info' && (!isInfoEligible || !storeOpsInfo)) return false;
    return true;
  });

  // Track desktop vs mobile so panel resize is only active on larger screens.
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const mq = window.matchMedia(DESKTOP_MEDIA_QUERY);
    const onChange = (e) => setIsDesktop(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  // Left-edge resize handle: hold and drag to stretch the panel width (desktop only).
  const handleResizeMove = useCallback((e) => {
    const st = resizeRef.current;
    if (!st.active) return;
    const delta = st.startX - e.clientX; // drag left → wider
    const maxWidth = Math.min(window.innerWidth - 60, 1100);
    const next = Math.max(MIN_PANEL_WIDTH, Math.min(st.startWidth + delta, maxWidth));
    setPanelWidth(next);
  }, []);

  const handleResizeEnd = useCallback(() => {
    resizeRef.current.active = false;
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    window.removeEventListener('pointermove', handleResizeMove);
    window.removeEventListener('pointerup', handleResizeEnd);
  }, [handleResizeMove]);

  const handleResizeStart = useCallback((e) => {
    if (e.pointerType === 'touch') return; // mobile keeps full-width layout
    e.preventDefault();
    resizeRef.current = { active: true, startX: e.clientX, startWidth: panelWidth };
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    window.addEventListener('pointermove', handleResizeMove);
    window.addEventListener('pointerup', handleResizeEnd);
  }, [panelWidth, handleResizeMove, handleResizeEnd]);

  useEffect(() => () => {
    window.removeEventListener('pointermove', handleResizeMove);
    window.removeEventListener('pointerup', handleResizeEnd);
  }, [handleResizeMove, handleResizeEnd]);

  const handleResetWidth = useCallback(() => setPanelWidth(DEFAULT_PANEL_WIDTH), []);

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
    if (!FEATURES.kpis) {
      setFinancials([]);
      setBudgetVsActual([]);
      setDoorCount([]);
      setDonations([]);
      setKeyMetrics(null);
      setTrends([]);
      setLoading(false);
      setError(null);
      setDoorCountError(null);
      setDonationsError(null);
      setKeyMetricsError(null);
      return;
    }
    setError(null);
    setDoorCountError(null);
    setDonationsError(null);
    setKeyMetricsError(null);

    let cancelled = false;
    const loadData = async () => {
      setLoading(true);
      try {
        const usesDailyGrain =
          !isConsolidated && (financialsPreset === 'This Month' || financialsPreset === 'Custom');
        const budgetGrain = usesDailyGrain ? 'day' : 'month';
        const usesMonthlyTrends = financialsPreset !== 'This Month';
        const kmPromise = isKeyMetricsEligible
          ? fetchKeyMetrics(location.id)
          : Promise.resolve({ data: null });
        const [finRes, dcRes, trRes, bvaRes, dnRes, kmRes] = await Promise.allSettled([
          fetchFinancials(location.id, dateRange.start, dateRange.end, {
            thisMonth:
              !isConsolidated && (financialsPreset === 'This Month' || financialsPreset === 'Custom'),
          }),
          isConsolidated
            ? Promise.resolve({ data: [] })
            : fetchDoorCount(location.id, dateRange.start, dateRange.end),
          usesMonthlyTrends
            ? fetchTrends(location.id, { start: dateRange.start, end: dateRange.end })
            : Promise.resolve({ data: [] }),
          fetchBudgetVsActual(location.id, dateRange.start, dateRange.end, { grain: budgetGrain }),
          fetchDonations(location.id, dateRange.start, dateRange.end),
          kmPromise,
        ]);
        if (cancelled) return;
        if (finRes.status === 'fulfilled') setFinancials(finRes.value.data || []);
        if (bvaRes.status === 'fulfilled') {
          setBudgetVsActual(Array.isArray(bvaRes.value.data) ? bvaRes.value.data : []);
        } else {
          setBudgetVsActual([]);
        }
        if (dnRes.status === 'fulfilled') {
          const payload = dnRes.value.data;
          setDonations(Array.isArray(payload) ? payload : []);
        } else {
          setDonations([]);
          const err = dnRes.reason;
          const detail =
            err?.response?.data?.error ??
            (typeof err?.response?.data === 'string' ? err.response.data : null);
          setDonationsError(
            detail || err?.message || 'Could not load donations. Check SQL / tbl_Donation.',
          );
        }
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
        if (kmRes.status === 'fulfilled') {
          setKeyMetrics(kmRes.value.data || null);
        } else {
          setKeyMetrics(null);
          const err = kmRes.reason;
          const detail =
            err?.response?.data?.error ??
            (typeof err?.response?.data === 'string' ? err.response.data : null);
          setKeyMetricsError(
            detail || err?.message || 'Could not load key metrics. Check tbl_Locations / SQL.',
          );
        }
      } catch (e) {
        if (!cancelled) setError('Failed to load data. Please try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadData();
    return () => {
      cancelled = true;
    };
  }, [location?.id, dateRange.start, dateRange.end, financialsPreset, isConsolidated, isKeyMetricsEligible]);

  // Reset tab on new location
  useEffect(() => {
    setActiveTab(FEATURES.kpis ? 'financials' : availableTabs[0]?.id || null);
  }, [location?.id]);
  useEffect(() => {
    if (availableTabs.some((tab) => tab.id === activeTab)) return;
    setActiveTab(availableTabs[0]?.id || null);
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
  const lowestDoorDay = doorCount.length
    ? doorCount.reduce((min, d) =>
        (d.DonorVisits ?? Infinity) < (min.DonorVisits ?? Infinity) ? d : min)
    : {};

  // Donations KPIs — SUM(DonationAmt) per day from tbl_Donation (same presets as Financials/Door Count).
  const totalDonations = donations.reduce((s, d) => s + (d.Donations || 0), 0);
  const donationAvgDaily =
    doorCalendarDays > 0 ? Math.round(totalDonations / doorCalendarDays) : 0;
  const donationPeakDay = donations.reduce((max, d) =>
    (d.Donations || 0) > (max.Donations || 0) ? d : max, {});
  const donationLowestDay = donations.length
    ? donations.reduce((min, d) =>
        (d.Donations ?? Infinity) < (min.Donations ?? Infinity) ? d : min)
    : {};

  return (
    <div
      className={`absolute top-0 right-0 h-full w-full sm:w-[440px] z-40 transition-transform duration-350 ease-[cubic-bezier(0.16,1,0.3,1)] ${
        open ? 'translate-x-0' : 'translate-x-full'
      }`}
      style={isDesktop ? { width: `${panelWidth}px` } : undefined}
    >
      {/* Left-edge resize handle (desktop only): hold and drag to stretch the panel. */}
      {isDesktop && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize panel"
          onPointerDown={handleResizeStart}
          onDoubleClick={handleResetWidth}
          title="Drag to resize · double-click to reset"
          className="group absolute left-0 top-0 h-full w-2 -translate-x-1/2 z-50 cursor-col-resize flex items-center justify-center"
        >
          <div className="h-14 w-1.5 rounded-full bg-gwsa-border group-hover:bg-gwsa-accent transition-colors" />
          <div className="absolute flex items-center justify-center w-5 h-9 rounded-md bg-gwsa-surface border border-gwsa-border shadow-panel opacity-0 group-hover:opacity-100 transition-opacity">
            <GripVertical className="w-3.5 h-3.5 text-gwsa-text-muted" />
          </div>
        </div>
      )}
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
        {availableTabs.length > 0 && (
          <MetricSelector tabs={availableTabs} activeTab={activeTab} onTabChange={setActiveTab} />
        )}

        {/* Date Range (hidden for static Info tab) */}
        {FEATURES.kpis && activeTab !== 'info' && activeTab !== 'keymetrics' && (
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
          ) : !activeTab ? (
            <div className="space-y-3 pt-4">
              <p className="text-sm text-gwsa-text-muted">
                This external view includes the map and location details only.
              </p>
            </div>
          ) : (
            <>
              {activeTab === 'financials' && (
                <FinancialsTab
                  location={location}
                  data={financials}
                  budgetVsActual={budgetVsActual}
                  totalRevenue={totalRevenue}
                  financialsPreset={financialsPreset}
                  usesTotalCoreDaily={usesTotalCoreDaily}
                  totalIncome={totalIncome}
                  totalOperating={totalOperating}
                  weightedExpenseRatio={weightedExpenseRatio}
                  incomeChange={incomeChange}
                />
              )}
              {activeTab === 'keymetrics' && (
                <KeyMetricsTab metrics={keyMetrics} loadError={keyMetricsError} />
              )}
              {activeTab === 'donor-door' && (
                <DonorDoorTab
                  donationsData={donations}
                  totalDonations={totalDonations}
                  donationAvgDaily={donationAvgDaily}
                  donationPeakDay={donationPeakDay}
                  donationLowestDay={donationLowestDay}
                  donationsError={donationsError}
                  doorCountData={doorCount}
                  totalVisits={totalVisits}
                  doorAvgDaily={avgDaily}
                  doorPeakDay={peakDay}
                  doorLowestDay={lowestDoorDay}
                  doorCountError={doorCountError}
                  includeDoorCount={!isConsolidated}
                  preset={financialsPreset}
                  rangeStart={dateRange.start}
                  rangeEnd={dateRange.end}
                  calendarDays={doorCalendarDays}
                />
              )}
              {activeTab === 'trends' && (
                <TrendsTab
                  data={trends}
                  preset={financialsPreset}
                  rangeStart={dateRange.start}
                  rangeEnd={dateRange.end}
                  financialsData={financials}
                  doorCountData={doorCount}
                  donationsData={donations}
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
  budgetVsActual,
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
  const budgetGranularity = usesTotalCoreDaily ? 'day' : 'month';

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
        <BudgetVsActualChart data={budgetVsActual} granularity={budgetGranularity} />
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
      <BudgetVsActualChart data={budgetVsActual} granularity={budgetGranularity} />
    </div>
  );
}

/**
 * Actual vs Budget Core revenue (DailyCoreRevenueBudgetVsActual_NoSubCategory).
 * Daily points for This Month / Custom; monthly points for Rolling 3 months / YTD / 12 Months
 * so the chart stays readable. Budget shows as a dashed reference line vs the solid Actual line.
 */
function BudgetVsActualChart({ data, granularity }) {
  if (!Array.isArray(data) || data.length === 0) return null;

  const chartData = data
    .map((d) => ({
      date: typeof d.PeriodDate === 'string' ? d.PeriodDate.slice(0, 10) : d.PeriodDate,
      actual: Number(d.ActualRevenue ?? 0),
      budget: Number(d.BudgetRevenue ?? 0),
    }))
    .filter((d) => d.date);

  if (chartData.length === 0) return null;

  const totalActual = chartData.reduce((s, d) => s + d.actual, 0);
  const totalBudget = chartData.reduce((s, d) => s + d.budget, 0);
  const variance = totalActual - totalBudget;
  const attainment = totalBudget !== 0 ? totalActual / totalBudget : null;
  const aboveBudget = variance >= 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 px-0.5">
        <span className="text-[11px] text-gwsa-text-muted">
          Variance{' '}
          <strong className={aboveBudget ? 'text-gwsa-green' : 'text-gwsa-red'}>
            {aboveBudget ? '+' : ''}{formatCurrency(variance)}
          </strong>
          {attainment != null ? ` · ${formatPercent(attainment)} of budget` : ''}
        </span>
      </div>
      <TrendChart
        data={chartData}
        title="Actual vs Budget (Core revenue)"
        lines={[
          { key: 'actual', color: '#3B82F6', name: 'Actual' },
          { key: 'budget', color: '#F59E0B', name: 'Budget', dashed: true },
        ]}
        dateAxisGranularity={granularity}
      />
    </div>
  );
}

function KeyMetricsTab({ metrics, loadError }) {
  if (loadError) {
    return (
      <div className="rounded-lg border border-gwsa-red/40 bg-gwsa-red/10 px-3 py-2 text-xs text-gwsa-red mt-2">
        {loadError}
      </div>
    );
  }
  if (!metrics) {
    return (
      <p className="text-sm text-gwsa-text-muted pt-2">No key metrics available for this location.</p>
    );
  }

  const sqft = metrics.salesSquareFt;
  const spsf = metrics.salesPerSqFtAnnualized;
  const lease = metrics.leaseStatus;
  const leaseLabel =
    lease === 'LEASE' ? 'Leased' : lease === 'OWN' ? 'Owned' : 'Unknown';
  const locName = metrics.location?.LocName;

  return (
    <div className="space-y-4 pt-2">
      {locName ? (
        <p className="text-xs text-gwsa-text-muted">
          Location record: <strong className="text-gwsa-text-secondary">{locName}</strong>
          {metrics.location?.Tier ? ` · ${metrics.location.Tier}` : ''}
        </p>
      ) : (
        <p className="text-xs text-gwsa-text-muted">
          No row in tbl_Locations for this store id. Square footage KPIs may be unavailable.
        </p>
      )}
      <MetricCard
        label="Sales Square Ft"
        value={sqft != null ? formatNumber(sqft) : '—'}
        color="blue"
      />
      <MetricCard
        label="Sales per Sq Ft"
        value={spsf != null ? formatCurrency(spsf) : '—'}
        color="green"
      />
      <MetricCard
        label="Leased or Owned"
        value={leaseLabel}
        color={lease === 'LEASE' ? 'amber' : lease === 'OWN' ? 'cyan' : 'amber'}
      />
    </div>
  );
}

function DonorDoorTab({
  donationsData,
  totalDonations,
  donationAvgDaily,
  donationPeakDay,
  donationLowestDay,
  donationsError,
  doorCountData,
  totalVisits,
  doorAvgDaily,
  doorPeakDay,
  doorLowestDay,
  doorCountError,
  includeDoorCount,
  preset,
  rangeStart,
  rangeEnd,
  calendarDays,
}) {
  return (
    <div className="space-y-8 pt-2">
      <section className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gwsa-text-muted">
          Donations
        </h3>
        <DonationsTab
          embedded
          data={donationsData}
          totalDonations={totalDonations}
          avgDaily={donationAvgDaily}
          peakDay={donationPeakDay}
          lowestDay={donationLowestDay}
          preset={preset}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          calendarDays={calendarDays}
          loadError={donationsError}
        />
      </section>
      {includeDoorCount ? (
        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gwsa-text-muted">
            Door Count
          </h3>
          <DoorCountTab
            embedded
            data={doorCountData}
            totalVisits={totalVisits}
            avgDaily={doorAvgDaily}
            peakDay={doorPeakDay}
            lowestDay={doorLowestDay}
            preset={preset}
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            calendarDays={calendarDays}
            loadError={doorCountError}
          />
        </section>
      ) : null}
    </div>
  );
}

function DonationsTab({
  data,
  totalDonations,
  avgDaily,
  peakDay,
  lowestDay,
  preset,
  rangeStart,
  rangeEnd,
  calendarDays,
  loadError,
  embedded = false,
}) {
  const periodLine = `${preset} · ${formatDateShort(rangeStart)} – ${formatDateShort(rangeEnd)}`;
  const fmtDay = (raw) =>
    raw != null
      ? formatDateShort(typeof raw === 'string' ? raw.slice(0, 10) : String(raw))
      : null;
  const peakDate = fmtDay(peakDay.DonationDate);
  const lowestDate = fmtDay(lowestDay.DonationDate);

  const chartSeries = data.length <= 120 ? data : data.slice(-120);
  const chartData = chartSeries.map((d) => ({
    date: d.DonationDate,
    value: d.Donations,
  }));

  return (
    <div className={`space-y-4 ${embedded ? '' : 'pt-2'}`}>
      {loadError ? (
        <div className="rounded-lg border border-gwsa-red/40 bg-gwsa-red/10 px-3 py-2 text-xs text-gwsa-red">
          {loadError}
        </div>
      ) : null}

      {!loadError && data.length === 0 ? (
        <p className="text-sm text-gwsa-text-muted">
          No donation rows for this store and date range. Confirm{' '}
          <code className="text-[11px] bg-gwsa-bg px-1 rounded">tbl_Donation.Storeid</code> matches this
          location.
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-3">
        <MetricCard
          label="Total donations"
          value={formatNumber(totalDonations)}
          color="green"
          subtext={periodLine}
        />
        <MetricCard
          label="Daily average"
          value={formatNumber(avgDaily)}
          color="blue"
          subtext={`Total ÷ ${calendarDays} calendar days`}
        />
        <MetricCard
          label="Peak day"
          value={formatNumber(peakDay.Donations || 0)}
          subtext={peakDate ? `${peakDate} · highest` : '—'}
          color="amber"
        />
        <MetricCard
          label="Lowest day"
          value={formatNumber(lowestDay.Donations || 0)}
          subtext={lowestDate ? `${lowestDate} · lowest with data` : '—'}
          color="cyan"
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
            title="Daily donations"
            lines={[{ key: 'value', color: '#10B981', name: 'Donations' }]}
            chartType="bar"
            dateAxisGranularity="day"
          />
        </>
      ) : null}
    </div>
  );
}

function DoorCountTab({
  data,
  totalVisits,
  avgDaily,
  peakDay,
  lowestDay,
  preset,
  rangeStart,
  rangeEnd,
  calendarDays,
  loadError,
  embedded = false,
}) {
  const periodLine = `${preset} · ${formatDateShort(rangeStart)} – ${formatDateShort(rangeEnd)}`;
  const fmtDay = (raw) =>
    raw != null
      ? formatDateShort(typeof raw === 'string' ? raw.slice(0, 10) : String(raw))
      : null;
  const peakDate = fmtDay(peakDay.CountDate);
  const lowestDate = fmtDay(lowestDay?.CountDate);

  const chartSeries =
    data.length <= 120 ? data : data.slice(-120);
  const chartData = chartSeries.map((d) => ({
    date: d.CountDate,
    value: d.DonorVisits,
  }));

  return (
    <div className={`space-y-4 ${embedded ? '' : 'pt-2'}`}>
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
          label="Lowest day"
          value={formatNumber(lowestDay?.DonorVisits || 0)}
          subtext={lowestDate ? `${lowestDate} · lowest In with data` : '—'}
          color="cyan"
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

function monthInRange(periodMonth, rangeStart, rangeEnd) {
  const mk = toMonthKey(periodMonth);
  if (!mk) return false;
  if (!rangeStart || !rangeEnd) return true;
  const lo = toMonthKey(rangeStart);
  const hi = toMonthKey(rangeEnd);
  return lo && hi && mk >= lo && mk <= hi;
}

function dayInRange(dayIso, rangeStart, rangeEnd) {
  if (!dayIso) return false;
  if (!rangeStart || !rangeEnd) return true;
  const key = String(dayIso).slice(0, 10);
  return key >= rangeStart && key <= rangeEnd;
}

function TrendsTab({
  data,
  preset,
  rangeStart,
  rangeEnd,
  financialsData,
  doorCountData,
  donationsData = [],
  includeDoorCount = true,
}) {
  const isThisMonth = preset === 'This Month';
  const DONATIONS_OPTION = { key: 'Donations', label: 'Donations', color: '#8B5CF6' };
  const metricOptions = isThisMonth
    ? [
        { key: 'NetRevenue', label: 'Revenue', color: '#3B82F6' },
        ...(includeDoorCount ? [{ key: 'DoorCount', label: 'Door Count', color: '#06B6D4' }] : []),
        DONATIONS_OPTION,
      ]
    : [
        { key: 'NetIncome', label: 'Net Income', color: '#10B981' },
        { key: 'NetRevenue', label: 'Revenue', color: '#3B82F6' },
        ...(includeDoorCount ? [{ key: 'DoorCount', label: 'Door Count', color: '#06B6D4' }] : []),
        DONATIONS_OPTION,
        { key: 'ExpenseRatio', label: 'Expense Ratio', color: '#F59E0B' },
      ];
  const [activeMetrics, setActiveMetrics] = useState(
    isThisMonth
      ? (includeDoorCount ? ['NetRevenue', 'DoorCount'] : ['NetRevenue'])
      : (includeDoorCount ? ['NetIncome', 'NetRevenue', 'DoorCount'] : ['NetIncome', 'NetRevenue']),
  );

  useEffect(() => {
    const allowedKeys = isThisMonth
      ? (includeDoorCount ? ['NetRevenue', 'DoorCount', 'Donations'] : ['NetRevenue', 'Donations'])
      : (includeDoorCount
          ? ['NetIncome', 'NetRevenue', 'DoorCount', 'Donations', 'ExpenseRatio']
          : ['NetIncome', 'NetRevenue', 'Donations', 'ExpenseRatio']);
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
        const blank = (key) => ({ date: key, NetRevenue: 0, DoorCount: 0, Donations: 0 });
        financialsData.forEach((row) => {
          const dt = row.SalesDate || row.PeriodMonth;
          if (!dt) return;
          const key = String(dt).slice(0, 10);
          const current = byDate.get(key) || blank(key);
          current.NetRevenue += Number(row.NetRevenue || row.TotalRevenue || 0);
          byDate.set(key, current);
        });
        if (includeDoorCount) {
          doorCountData.forEach((row) => {
            const dt = row.CountDate;
            if (!dt) return;
            const key = String(dt).slice(0, 10);
            const current = byDate.get(key) || blank(key);
            current.DoorCount += Number(row.DonorVisits || 0);
            byDate.set(key, current);
          });
        }
        donationsData.forEach((row) => {
          const dt = row.DonationDate;
          if (!dt) return;
          const key = String(dt).slice(0, 10);
          const current = byDate.get(key) || blank(key);
          current.Donations += Number(row.Donations || 0);
          byDate.set(key, current);
        });
        return Array.from(byDate.values())
          .filter((row) => dayInRange(row.date, rangeStart, rangeEnd))
          .sort((a, b) => a.date.localeCompare(b.date));
      })()
    : (() => {
        // Monthly trends: prefer Donations from API (SQL monthly rollup); fallback to daily rows.
        const donationsByMonth = new Map();
        donationsData.forEach((row) => {
          const monthKey = toMonthKey(row.DonationDate);
          if (!monthKey) return;
          donationsByMonth.set(
            monthKey,
            (donationsByMonth.get(monthKey) || 0) + Number(row.Donations || 0),
          );
        });
        return data
          .filter((d) => monthInRange(d.PeriodMonth, rangeStart, rangeEnd))
          .map((d) => {
          const monthKey = toMonthKey(d.PeriodMonth);
          const donationsValue =
            d.Donations != null && d.Donations !== ''
              ? Number(d.Donations)
              : (monthKey ? donationsByMonth.get(monthKey) : null);
          return {
            date: d.PeriodMonth,
            ...Object.fromEntries(
              activeMetrics.map((k) => [
                k,
                k === 'Donations'
                  ? (donationsValue ?? 0)
                  : d[k],
              ]),
            ),
          };
        });
      })();

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
