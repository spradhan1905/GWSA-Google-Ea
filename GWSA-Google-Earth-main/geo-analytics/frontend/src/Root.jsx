import React, { useState, useEffect } from 'react';
import App from './App';
import Landing from './components/Landing/Landing';

export default function Root() {
  const [showLanding, setShowLanding] = useState(true);

  useEffect(() => {
    const stored = window.sessionStorage.getItem('gwsa-show-landing');
    if (stored === 'false') {
      setShowLanding(false);
    }
  }, []);

  const handleEnter = () => {
    window.sessionStorage.setItem('gwsa-show-landing', 'false');
    setShowLanding(false);
  };

  const handleBackToLanding = () => {
    window.sessionStorage.setItem('gwsa-show-landing', 'true');
    setShowLanding(true);
  };

  if (showLanding) {
    return <Landing onEnter={handleEnter} />;
  }

  return <App onBackToLanding={handleBackToLanding} />;
}

