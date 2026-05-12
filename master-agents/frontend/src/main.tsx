import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import '@ui5/webcomponents-react/styles.css'
import '@ui5/webcomponents-react/dist/Assets.js'
import { setTheme } from '@ui5/webcomponents-base/dist/config/Theme.js'

if (typeof window !== 'undefined') {
  const THEME_STORAGE_KEY = 'fiori-chat-theme'
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY) as 'light' | 'dark' | 'system' | null
  const preferredMode = stored ?? 'system'
  const systemMode: 'light' | 'dark' = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  const effectiveMode = preferredMode === 'system' ? systemMode : preferredMode
  const ui5Theme = effectiveMode === 'dark' ? 'sap_horizon_dark' : 'sap_horizon'
  setTheme(ui5Theme)
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <App />
)
