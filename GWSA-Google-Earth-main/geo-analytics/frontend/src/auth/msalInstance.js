/**
 * GWSA GeoAnalytics — single MSAL PublicClientApplication instance
 *
 * We initialize once at app startup (see initMsal()), then share the same
 * instance with both <MsalProvider> and the axios request interceptor.
 */
import { PublicClientApplication, EventType } from '@azure/msal-browser';
import { msalConfig, authConfigured, apiTokenRequest } from './msalConfig';

export const msalInstance = new PublicClientApplication(msalConfig);

let initialized = false;

export async function initMsal() {
  if (initialized) return;
  initialized = true;

  if (!authConfigured) {
    console.warn(
      '[auth] MSAL env vars missing: running in unauthenticated mode. ' +
      'Set VITE_AZURE_TENANT_ID, VITE_AZURE_CLIENT_ID, VITE_AZURE_API_SCOPE to enable sign-in.'
    );
    return;
  }

  await msalInstance.initialize();

  // Handle the redirect back from Microsoft (if we just returned from loginRedirect).
  try {
    const result = await msalInstance.handleRedirectPromise();
    if (result?.account) {
      msalInstance.setActiveAccount(result.account);
    }
  } catch (err) {
    console.error('[auth] handleRedirectPromise failed', err);
  }

  const accounts = msalInstance.getAllAccounts();
  if (!msalInstance.getActiveAccount() && accounts.length > 0) {
    msalInstance.setActiveAccount(accounts[0]);
  }

  msalInstance.addEventCallback((event) => {
    if (event.eventType === EventType.LOGIN_SUCCESS && event.payload?.account) {
      msalInstance.setActiveAccount(event.payload.account);
    }
  });
}

/** Acquire an access token for our backend API, silently if possible. */
export async function getApiAccessToken() {
  if (!authConfigured) return null;
  const account = msalInstance.getActiveAccount();
  if (!account) return null;
  try {
    const response = await msalInstance.acquireTokenSilent({
      ...apiTokenRequest,
      account,
    });
    return response.accessToken;
  } catch (err) {
    if (err?.name === 'InteractionRequiredAuthError') {
      await msalInstance.acquireTokenRedirect(apiTokenRequest);
      return null;
    }
    console.error('[auth] acquireTokenSilent failed', err);
    return null;
  }
}
