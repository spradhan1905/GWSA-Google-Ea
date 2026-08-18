import React from 'react';
import * as Switch from '@radix-ui/react-switch';
import { caretDown24 } from '@esri/calcite-ui-icons/js/caretDown24.js';
import { users24 } from '@esri/calcite-ui-icons/js/users24.js';
import { Loader2 } from 'lucide-react';
import { useMapControls } from '../../context/MapControlsContext';
import { INCOME_COLORS } from '../Map/MedianIncomeLayer';
import CalciteIcon from '../Shell/CalciteIcon';

function formatMoney(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return 'N/A';
  return `$${number.toLocaleString()}`;
}

export default function DemographicsSection() {
  const {
    incomeLayerOn,
    setIncomeLayerOn,
    incomeLayerStatus,
  } = useMapControls();
  const breaks = incomeLayerStatus.meta?.income_breaks || [];

  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3.5 text-sm font-semibold text-gwsa-text hover:bg-gwsa-surface-hover">
        <CalciteIcon path={users24} className="h-4 w-4 text-gwsa-green" />
        <span>Demographics</span>
        <CalciteIcon path={caretDown24} className="ml-auto h-3 w-3 text-gwsa-text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="px-4 pb-4">
        <div className="flex items-center justify-between gap-4 rounded-md border border-gwsa-border bg-gwsa-surface p-3">
          <div>
            <label htmlFor="median-income-layer" className="text-sm font-semibold text-gwsa-text">
              Median household income
            </label>
            <p className="mt-1 text-xs leading-relaxed text-gwsa-text-secondary">
              Census-tract income estimates. Darker green indicates higher income.
            </p>
          </div>
          <Switch.Root
            id="median-income-layer"
            checked={incomeLayerOn}
            onCheckedChange={setIncomeLayerOn}
            aria-label="Show median household income layer"
            className="inline-flex h-5 w-9 shrink-0 items-center rounded-full bg-gwsa-border-light p-0.5 outline-none transition-colors data-[state=checked]:bg-gwsa-accent focus-visible:ring-2 focus-visible:ring-gwsa-accent focus-visible:ring-offset-2"
          >
            <Switch.Thumb
              className="block h-4 w-4 rounded-full bg-white shadow-sm transition-transform data-[state=checked]:translate-x-4"
            />
          </Switch.Root>
        </div>

        {incomeLayerOn && incomeLayerStatus.loading && (
          <p className="mt-3 flex items-center gap-2 text-xs text-gwsa-text-secondary">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            Loading census tracts…
          </p>
        )}

        {incomeLayerOn && incomeLayerStatus.error && (
          <p role="alert" className="mt-3 rounded-lg border border-gwsa-red/30 bg-gwsa-red/10 p-2 text-xs text-red-700">
            {incomeLayerStatus.error}
          </p>
        )}

        {incomeLayerOn && incomeLayerStatus.ready && breaks.length > 1 && (
          <div className="mt-3 space-y-1" aria-label="Median income legend">
            {breaks.slice(1).map((low, index) => {
              const high = breaks[index + 2];
              return (
                <div key={low} className="flex items-center gap-2 text-[11px] text-gwsa-text-secondary">
                  <span
                    className="h-3 w-5 shrink-0 rounded-sm border border-gwsa-border-light"
                    style={{ backgroundColor: INCOME_COLORS[Math.min(index, INCOME_COLORS.length - 1)] }}
                    aria-hidden
                  />
                  <span className="tabular-nums">
                    {formatMoney(low)}{high ? ` – ${formatMoney(high)}` : '+'}
                  </span>
                </div>
              );
            })}
            {incomeLayerStatus.hasNoData && (
              <p className="pt-1 text-[11px] text-gwsa-text-muted">Gray tracts have no ACS estimate.</p>
            )}
          </div>
        )}
      </div>
    </details>
  );
}
