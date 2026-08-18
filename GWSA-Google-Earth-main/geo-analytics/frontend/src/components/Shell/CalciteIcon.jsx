import React from 'react';

export default function CalciteIcon({ path, className, ...props }) {
  const paths = Array.isArray(path) ? path : [{ path }];

  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      focusable="false"
      aria-hidden
      {...props}
    >
      {paths.map((entry, index) => (
        <path
          key={index}
          d={entry.path}
          opacity={entry.opacity}
        />
      ))}
    </svg>
  );
}
