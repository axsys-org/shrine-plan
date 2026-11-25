import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'

// Global fetch interceptor to handle 401s across all pages
const originalFetch = window.fetch
window.fetch = async (...args) => {
  const response = await originalFetch(...args)
  
  if (response.status === 401) {
    const url = typeof args[0] === 'string' ? args[0] : args[0] instanceof URL ? args[0].toString() : ''
    if (url.includes('/api/') && !url.includes('/health')) {
      const session = localStorage.getItem('session')
      if (session) {
        const isAuthEndpoint = url.includes('/api/auth/')
        if (!isAuthEndpoint) {
          localStorage.removeItem('session')
          localStorage.removeItem('csrfToken')
          localStorage.removeItem('user')
          window.location.reload()
        }
      }
    }
  }
  
  return response
}

// No service worker under Shrine: drop any left from the hosted app so it
// cannot serve a stale build.
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => r.unregister()))
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename="/gematria">
      <App />
    </BrowserRouter>
  </StrictMode>,
)
