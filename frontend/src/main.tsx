import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { useAuthStore } from './store/authStore';
import { setTokenGetter } from './lib/api';

// Initialize API token getter to break circular dependency
setTokenGetter(() => useAuthStore.getState().token);


const root = document.getElementById('root');


if (root) {
  try {
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    )
  } catch (e) {
    console.error("React Render Error:", e);
    root.innerHTML = `<div style="color:red; font-size: 20px;">CRASH: ${e}</div>`;
  }
} else {
  console.error('Root element not found');
}
