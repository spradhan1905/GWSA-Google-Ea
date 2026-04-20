/**
 * GWSA GeoAnalytics — MSAL configuration
 *
 * Values come from Vite env vars so we don't hardcode tenant/client IDs:
 *   VITE_AZURE_TENANT_ID  — Entra tenant GUID
 *   VITE_AZURE_CLIENT_ID  — app registration (client) ID
 *   VITE_AZURE_API_SCOPE  — e.g. api://<client-id>/user_impersonation
 *
 * Redirect URI is inferred from window.location.origin, which must exactly
 * match a URI registered on the SPA platform of the app registration.
 */
import { LogLevel } from '@azure/msal-browser';

const tenantId = import.meta.env.VITE_AZURE_TENANT_ID;
const clientId = import.meta.env.VITE_AZURE_CLIENT_ID;
const apiScope = import.meta.env.VITE_AZURE_API_SCOPE;

export const authConfigured = Boolean(tenantId && clientId && apiScope);

export const msalConfig = {
  auth: {
    clientId: clientId || '00000000-0000-0000-0000-000000000000',
    authority: `https://login.microsoftonline.com/${tenantId || 'common'}`,
    redirectUri: typeof window !== 'undefined' ? window.location.origin : '/',
    postLogoutRedirectUri: typeof window !== 'undefined' ? window.location.origin : '/',
    navigateToLoginRequestUrl: true,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        if (level === LogLevel.Error) console.error('[MSAL]', message);
      },
    },
  },
};

export const loginRequest = {
  scopes: apiScope ? [apiScope] : [],
};

export const apiTokenRequest = {
  scopes: apiScope ? [apiScope] : [],
};
