/**
 * Application Entry Point
 *
 * WHAT: React application bootstrap file.
 *
 * WHY: Sets up React root and renders the main App component.
 *
 * HOW: Uses React 18's createRoot API for concurrent features.
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
