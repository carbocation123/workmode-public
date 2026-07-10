import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { setApiBase } from './api'
import { initializeDesktop } from './desktop'
import './styles.css'

async function bootstrap() {
  const root = ReactDOM.createRoot(document.getElementById('root')!)
  try {
    const desktop = await initializeDesktop()
    if (desktop) setApiBase(desktop.apiBase)
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    )
  } catch (error) {
    root.render(
      <div className="desktop-startup-error">
        <h1>Workmode Public 启动失败</h1>
        <p>{error instanceof Error ? error.message : String(error)}</p>
        <p>请重新启动应用；详细信息位于用户数据目录的 logs 文件夹。</p>
      </div>
    )
  }
}

bootstrap()
