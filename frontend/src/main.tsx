import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './styles/global.css'
import { initBridge } from './bridge'

const root = createRoot(document.getElementById('root')!)

initBridge().then(() => {
  root.render(
    <StrictMode>
      <App />
    </StrictMode>
  )
})