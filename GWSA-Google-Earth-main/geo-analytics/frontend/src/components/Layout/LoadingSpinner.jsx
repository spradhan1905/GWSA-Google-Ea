/**
 * GWSA GeoAnalytics — Loading Spinner
 */
import React from 'react';

export default function LoadingSpinner({ size = 'md', text = '' }) {
  const sizes = {
    sm: 'w-5 h-5 border-2',
    md: 'w-8 h-8 border-2',
    lg: 'w-12 h-12 border-3',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <div className={`${sizes[size]} border-gwsa-border border-t-gwsa-accent rounded-full animate-spin`} />
      {text && <p className="text-sm text-gwsa-text-muted animate-pulse-soft">{text}</p>}
    </div>
  );
}
