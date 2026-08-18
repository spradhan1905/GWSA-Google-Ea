import React, { useEffect, useRef } from 'react';
import { x24 } from '@esri/calcite-ui-icons/js/x24.js';
import CalciteIcon from './CalciteIcon';

export default function RailPanel({
  title,
  description,
  onClose,
  children,
  footer,
  mobile = false,
  dragHandleProps,
}) {
  const panelRef = useRef(null);

  useEffect(() => {
    panelRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <section
      ref={panelRef}
      tabIndex={-1}
      role="region"
      aria-label={title}
      className={`flex h-full w-full flex-col overflow-hidden bg-gwsa-surface outline-none ${
        mobile
          ? 'rounded-t-2xl border border-b-0 border-gwsa-border shadow-panel animate-slide-up'
          : 'w-panel shrink-0 border-r border-gwsa-border animate-slide-in-left'
      }`}
    >
      {mobile && (
        <button
          type="button"
          aria-label={`Drag down to close ${title}`}
          className="flex shrink-0 touch-none justify-center pb-1 pt-2 cursor-grab active:cursor-grabbing"
          {...dragHandleProps}
        >
          <span className="h-1 w-10 rounded-full bg-gwsa-border-light" aria-hidden />
        </button>
      )}
      <header className="flex shrink-0 items-start justify-between gap-2 border-b border-gwsa-border px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-gwsa-text">{title}</h2>
          {description && (
            <p className="mt-0.5 text-xs text-gwsa-text-secondary">{description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={`Close ${title}`}
          className="shrink-0 rounded-sm p-1.5 text-gwsa-text-muted hover:bg-gwsa-surface-hover hover:text-gwsa-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gwsa-accent"
        >
          <CalciteIcon path={x24} className="h-4 w-4" />
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      {footer && (
        <footer className="shrink-0 border-t border-gwsa-border">{footer}</footer>
      )}
    </section>
  );
}
