import React from 'react';
import ReactDOM from 'react-dom/client';
import { MsalProvider } from '@azure/msal-react';
import Root from './Root';
import { msalInstance, initMsal } from './auth/msalInstance';
import './index.css';

// Load Google Maps API dynamically from env
const MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
if (MAPS_KEY && MAPS_KEY !== 'your_maps_key_here') {
  const script = document.createElement('script');
  script.src = `https://maps.googleapis.com/maps/api/js?key=${MAPS_KEY}&libraries=places,geometry`;
  script.async = true;
  script.defer = true;
  document.head.appendChild(script);
}

// MSAL must finish handleRedirectPromise() before React renders so we never
// render the app in a stale "not signed in" state right after a login redirect.
initMsal().finally(() => {
  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <MsalProvider instance={msalInstance}>
        <Root />
      </MsalProvider>
    </React.StrictMode>
  );
});
