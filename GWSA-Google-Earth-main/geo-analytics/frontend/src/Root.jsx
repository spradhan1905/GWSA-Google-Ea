import React from 'react';
import { AuthenticatedTemplate, UnauthenticatedTemplate } from '@azure/msal-react';
import App from './App';
import LoginScreen from './auth/LoginScreen';
import { authConfigured } from './auth/msalConfig';

export default function Root() {
  // If MSAL env vars are missing (e.g. local dev without auth), skip the gate
  // entirely so developers can still iterate on UI with demo data.
  if (!authConfigured) {
    return <App />;
  }

  return (
    <>
      <AuthenticatedTemplate>
        <App />
      </AuthenticatedTemplate>
      <UnauthenticatedTemplate>
        <LoginScreen />
      </UnauthenticatedTemplate>
    </>
  );
}
