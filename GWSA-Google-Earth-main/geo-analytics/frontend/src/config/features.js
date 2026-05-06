const toBool = (value, defaultValue = true) => {
  if (value == null || value === '') return defaultValue;
  return !['false', '0', 'no', 'off'].includes(String(value).trim().toLowerCase());
};

export const FEATURES = {
  ai: toBool(import.meta.env.VITE_ENABLE_AI, true),
  kpis: toBool(import.meta.env.VITE_ENABLE_KPIS, true),
};
