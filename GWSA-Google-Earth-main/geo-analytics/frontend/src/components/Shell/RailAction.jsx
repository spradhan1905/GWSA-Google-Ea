import React from 'react';
import CalciteIcon from './CalciteIcon';

export default function RailAction({
  iconPath,
  label,
  active = false,
  disabled = false,
  badge,
  mobile = false,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-current={active ? 'true' : undefined}
      aria-label={badge ? `${label} (${badge})` : label}
      title={badge ? `${label}: ${badge}` : label}
      className={`relative flex items-center justify-center transition-colors duration-150 ${
        mobile
          ? 'h-full flex-1 flex-col gap-1 border-t-2 text-[10px] font-semibold'
          : 'h-12 w-full border-l-2'
      } ${
        active
          ? mobile
            ? 'border-gwsa-accent bg-gwsa-rail-active-bg text-gwsa-accent'
            : 'border-gwsa-accent bg-gwsa-rail-active-bg text-gwsa-accent'
          : mobile
            ? 'border-transparent text-gwsa-text-secondary hover:bg-gwsa-surface-hover hover:text-gwsa-text'
            : 'border-transparent text-gwsa-text-secondary hover:bg-gwsa-surface-hover hover:text-gwsa-text'
      } ${
        disabled
          ? 'cursor-not-allowed opacity-40 hover:bg-transparent'
          : ''
      }`}
    >
      <CalciteIcon path={iconPath} className="h-6 w-6" />
      {mobile && <span>{label}</span>}
      {badge && (
        <span className={`${mobile ? 'absolute right-2 top-1' : 'absolute right-1 top-1'} rounded-sm bg-amber-100 px-1 py-px text-[8px] font-bold uppercase leading-none tracking-wide text-amber-800`}>
          {badge}
        </span>
      )}
    </button>
  );
}
