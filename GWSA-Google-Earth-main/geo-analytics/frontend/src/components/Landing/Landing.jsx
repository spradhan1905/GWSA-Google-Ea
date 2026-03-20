import React from 'react';

export default function Landing({ onEnter }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-slate-100 to-slate-200 text-slate-900 flex flex-col">
      <header className="w-full border-b border-slate-200 bg-white/90 backdrop-blur-md">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-md bg-white shadow-sm border border-slate-200 flex items-center justify-center">
              <span className="text-lg font-bold text-sky-700">G</span>
            </div>
            <div>
              <p className="text-xs font-semibold tracking-[0.2em] text-slate-500 uppercase">
                GWSA GeoAnalytics
              </p>
              <p className="text-sm text-slate-700">
                Goodwill Industries of San Antonio
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 text-xs text-slate-500">
              <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 mr-1" />
              Live map of stores, donation centers, and outlets
            </div>
            <button
              type="button"
              onClick={onEnter}
              className="inline-flex items-center gap-2 rounded-full bg-sky-500 px-4 py-2 text-xs font-semibold tracking-wide uppercase text-white shadow-lg shadow-sky-500/50 hover:bg-sky-400 transition-colors"
            >
              Open GeoAnalytics
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-6xl px-6 py-10 grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-10 items-center">
          {/* Hero copy */}
          <section className="space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
              <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Store & donor analytics on a living map
            </div>
            <div>
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-slate-900">
                See every Goodwill location
                <span className="block text-sky-600">in one geospatial view.</span>
              </h1>
              <p className="mt-4 text-sm sm:text-base text-slate-600 leading-relaxed max-w-xl">
                GWSA GeoAnalytics brings retail stores, donation stations, outlets and donor
                catchments together on a single map. Explore performance, traffic, and
                community reach — visually.
              </p>
            </div>

            {/* Feature grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] font-medium text-slate-500 uppercase tracking-[0.18em]">
                  Locations
                </p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">36</p>
                <p className="mt-1 text-xs text-slate-500">
                  Retail stores, donation centers, outlets, and more across South Texas.
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] font-medium text-slate-500 uppercase tracking-[0.18em]">
                  Layers
                </p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">3</p>
                <p className="mt-1 text-xs text-slate-500">
                  Financials, donor traffic, and donor address heatmaps.
                </p>
              </div>
              <div className="rounded-2xl border border-sky-500/40 bg-sky-50 p-4 shadow-sm">
                <p className="text-[11px] font-medium text-sky-700 uppercase tracking-[0.18em]">
                  Gemini AI
                </p>
                <p className="mt-1 text-2xl font-semibold text-sky-700">Ask the map</p>
                <p className="mt-1 text-xs text-sky-800/80">
                  Use natural language to compare locations and surface insights.
                </p>
              </div>
            </div>

            {/* Primary CTA */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                type="button"
                onClick={onEnter}
                className="inline-flex items-center gap-2 rounded-xl bg-sky-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-sky-500/50 hover:bg-sky-400 transition-colors"
              >
                Launch live map
              </button>
              <span className="text-xs text-slate-400">
                Satellite-first view with Waze directions, distance tools, and AI chat.
              </span>
            </div>
          </section>

          {/* Visual preview card */}
          <section className="relative">
            <div className="absolute -inset-6 bg-sky-300/40 blur-3xl opacity-70 pointer-events-none" />
            <div className="relative rounded-3xl border border-slate-200 bg-white shadow-xl overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                  <p className="text-xs font-medium text-slate-800">San Antonio &amp; South Texas</p>
                </div>
                <p className="text-[11px] text-slate-500">Satellite · Analytics overlay preview</p>
              </div>
              <div className="aspect-[4/3] bg-gradient-to-br from-slate-200 via-slate-100 to-slate-200 relative">
                <div className="absolute inset-6 rounded-2xl border border-slate-300 bg-slate-50 overflow-hidden">
                  {/* Simple mock map grid */}
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_#38bdf8_0,_transparent_45%),radial-gradient(circle_at_bottom,_#22c55e_0,_transparent_55%)] opacity-80" />
                  <div className="absolute inset-4 grid grid-cols-4 grid-rows-3 gap-4">
                    <div className="rounded-full bg-sky-500/90 shadow-md self-start justify-self-start w-6 h-6" />
                    <div className="rounded-full bg-emerald-500/90 shadow-md self-center justify-self-center w-6 h-6" />
                    <div className="rounded-full bg-sky-500/90 shadow-md self-end justify-self-end w-6 h-6" />
                    <div className="rounded-full bg-amber-400/90 shadow-md self-center justify-self-start w-6 h-6" />
                  </div>
                </div>
                <div className="absolute left-5 bottom-5 flex flex-wrap gap-2">
                  <span className="inline-flex items-center gap-2 rounded-full bg-slate-900/90 px-3 py-1.5 text-[11px] text-slate-50 border border-slate-800/80">
                    <span className="inline-flex h-2 w-2 rounded-full bg-sky-400" />
                    Retail store
                  </span>
                  <span className="inline-flex items-center gap-2 rounded-full bg-slate-900/90 px-3 py-1.5 text-[11px] text-slate-50 border border-slate-800/80">
                    <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                    Donation center
                  </span>
                  <span className="inline-flex items-center gap-2 rounded-full bg-slate-900/90 px-3 py-1.5 text-[11px] text-slate-50 border border-slate-800/80">
                    <span className="inline-flex h-2 w-2 rounded-full bg-amber-400" />
                    Outlet
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

