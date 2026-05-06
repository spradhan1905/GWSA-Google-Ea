/**
 * GWSA GeoAnalytics — Sign-in screen
 * Shown when the user is not authenticated. One click → Microsoft redirect.
 */
import React, { useState } from 'react';
import { useMsal } from '@azure/msal-react';
import { LogIn, ShieldCheck } from 'lucide-react';
import { loginRequest } from './msalConfig';

const GWSA_LOGO_URL = '/assets/goodwill-san-antonio-logo.png';

export default function LoginScreen() {
  const { instance } = useMsal();
  const [signingIn, setSigningIn] = useState(false);
  const [error, setError] = useState(null);

  const handleSignIn = async () => {
    setError(null);
    setSigningIn(true);
    try {
      await instance.loginRedirect(loginRequest);
    } catch (err) {
      console.error('[auth] loginRedirect failed', err);
      setError(err?.errorMessage || err?.message || 'Sign-in failed. Please try again.');
      setSigningIn(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 via-slate-100 to-slate-200 px-6">
      <div className="w-full max-w-md rounded-2xl bg-white/95 backdrop-blur-md border border-slate-200 shadow-xl p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-11 h-11 rounded-xl bg-white flex items-center justify-center shadow-md overflow-hidden">
            <img
              src={GWSA_LOGO_URL}
              alt=""
              className="w-full h-full object-contain"
              aria-hidden
            />
          </div>
          <div>
            <p className="text-[11px] font-semibold tracking-[0.2em] text-slate-500 uppercase">
              GWSA GeoAnalytics
            </p>
            <p className="text-sm font-medium text-slate-800">
              Goodwill Industries of San Antonio
            </p>
          </div>
        </div>

        <h1 className="text-2xl font-semibold text-slate-900 mb-2">Sign in to continue</h1>
        <p className="text-sm text-slate-600 mb-6">
          This tool is restricted to Goodwill Industries of San Antonio employees.
          Sign in with your GWSA Microsoft account to access live store, donation,
          and revenue analytics.
        </p>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={handleSignIn}
          disabled={signingIn}
          className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-60 disabled:cursor-not-allowed px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-sky-500/30 transition-colors"
        >
          <LogIn className="w-4 h-4" />
          {signingIn ? 'Redirecting to Microsoft…' : 'Sign in with Microsoft'}
        </button>

        <div className="mt-6 flex items-start gap-2 text-xs text-slate-500">
          <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0 text-emerald-600" />
          <p>
            Your credentials never touch this app. Authentication is handled
            directly by Microsoft Entra ID, and only a short-lived access token
            is used to reach the GWSA analytics API.
          </p>
        </div>
      </div>
    </div>
  );
}
