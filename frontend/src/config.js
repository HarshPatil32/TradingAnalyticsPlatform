// Reads and validates required env variables at startup
// Keep vercel.json CSP connect-src in sync with FALLBACK_URL / VITE_API_URL.
const FALLBACK_URL = 'https://mytradingbot-project.onrender.com';
const rawApiUrl = import.meta.env.VITE_API_URL?.trim();

if (!rawApiUrl) {
  if (import.meta.env.PROD) {
    console.error('[config] VITE_API_URL is not set in a production build.');
  } else {
    console.warn(
      '[config] VITE_API_URL is not set. Falling back to ' + FALLBACK_URL + '. ' +
      'Create frontend/.env.local from .env.example to point at your local backend.'
    );
  }
}

export const API_URL = rawApiUrl || FALLBACK_URL;
