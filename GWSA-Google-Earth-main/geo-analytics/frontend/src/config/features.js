const toBool = (value, defaultValue = true) => {
  if (value == null || value === '') return defaultValue;
  return !['false', '0', 'no', 'off'].includes(String(value).trim().toLowerCase());
};

export const FEATURES = {
  ai: toBool(import.meta.env.VITE_ENABLE_AI, true),
  kpis: toBool(import.meta.env.VITE_ENABLE_KPIS, true),
  layers: toBool(import.meta.env.VITE_ENABLE_LAYERS, true),
  tools: toBool(import.meta.env.VITE_ENABLE_TOOLS, true),
  analytics: toBool(import.meta.env.VITE_ENABLE_ANALYTICS, false),
  reports: toBool(import.meta.env.VITE_ENABLE_REPORTS, false),
  competitorLayer: toBool(import.meta.env.VITE_ENABLE_COMPETITOR_LAYER, false),
};
