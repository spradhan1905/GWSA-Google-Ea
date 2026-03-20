/**
 * GWSA GeoAnalytics — Formatters
 * Number, currency, date formatting utilities.
 */

export const formatCurrency = (value) => {
  if (value == null || isNaN(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

export const formatCurrencyFull = (value) => {
  if (value == null || isNaN(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

export const formatPercent = (value) => {
  if (value == null || isNaN(value)) return '—';
  return `${(value * 100).toFixed(1)}%`;
};

export const formatNumber = (value) => {
  if (value == null || isNaN(value)) return '—';
  return new Intl.NumberFormat('en-US').format(value);
};

export const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
};

export const formatDateFull = (dateStr) => {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

export const getChangeIndicator = (current, previous) => {
  if (current == null || previous == null || previous === 0) return { direction: 'flat', percent: 0 };
  const change = ((current - previous) / Math.abs(previous)) * 100;
  return {
    direction: change > 0 ? 'up' : change < 0 ? 'down' : 'flat',
    percent: Math.abs(change).toFixed(1),
  };
};
