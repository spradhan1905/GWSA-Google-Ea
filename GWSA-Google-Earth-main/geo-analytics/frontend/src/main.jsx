import React from 'react';
import ReactDOM from 'react-dom/client';
import Root from './Root';
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

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
