import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

import './styles/global.css'

// 全局未捕获错误兜底：ErrorBoundary 只能捕获渲染错误，异步 / 事件 handler 错误
// 必须靠 window.onerror / unhandledrejection 兜底。这里统一打到 console，
// 方便排查；如需上报到 Sentry 等，替换 console.error 即可。
window.addEventListener('error', (event) => {
  console.error('[window.onerror]', event.error || event.message, event)
})
window.addEventListener('unhandledrejection', (event) => {
  console.error('[unhandledrejection]', event.reason)
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
