/**
 * YYYY-MM-DD in the browser's local timezone.
 * toISOString() uses UTC and can shift the calendar day vs Central Time.
 */
export function localDateISO(d) {
  const x = new Date(d);
  const y = x.getFullYear();
  const m = String(x.getMonth() + 1).padStart(2, '0');
  const day = String(x.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Inclusive calendar-day span for YYYY-MM-DD strings (local noon avoids DST edge cases). */
export function calendarDaysInclusive(isoStart, isoEnd) {
  if (!isoStart || !isoEnd) return 0;
  const s = new Date(`${isoStart}T12:00:00`);
  const e = new Date(`${isoEnd}T12:00:00`);
  const ms = e - s;
  if (ms < 0) return 0;
  return Math.floor(ms / 86400000) + 1;
}

export function formatDateShort(iso) {
  if (!iso) return '';
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Normalize any API date to the first day of its calendar month (YYYY-MM-01). */
export function toMonthKey(dateLike) {
  if (dateLike == null || dateLike === '') return null;
  const s = String(dateLike);
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    return `${s.slice(0, 7)}-01`;
  }
  const d = new Date(s.includes('T') ? s : `${s}T12:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}-01`;
}
