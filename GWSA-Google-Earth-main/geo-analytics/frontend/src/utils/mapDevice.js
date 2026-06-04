/** Match Tailwind `sm` breakpoint — map toolbar / layer behavior. */
export const MOBILE_MAP_QUERY = '(max-width: 639px)';

export function getIsMobileMap() {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_MAP_QUERY).matches;
}
