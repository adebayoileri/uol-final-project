import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { MotionConfig } from 'motion/react'
import App from './App.tsx'
import { ToastProvider } from './components/ui/Toast'
import { springDefault } from './motion/springs'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      {/*
        reducedMotion="user" drops transform/layout animation and keeps
        opacity and colour, which is the gentler non-vestibular equivalent —
        not the absence of feedback. Set once here so no component has to
        check the media query itself.
      */}
      <MotionConfig reducedMotion="user" transition={springDefault}>
        <ToastProvider>
          <App />
        </ToastProvider>
      </MotionConfig>
    </BrowserRouter>
  </StrictMode>,
)
