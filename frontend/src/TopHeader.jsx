import { useEffect, useState } from 'react'

const VIEW_LABELS = {
  overview: 'Overview',
  live: 'Live Logs',
  anomalies: 'Anomalies',
  analytics: 'Analytics',
}

export default function TopHeader({ view, totalLogs, lastUpdated, onRefresh, onMenuClick }) {
  const [secondsAgo, setSecondsAgo] = useState(0)

  useEffect(() => {
    const t = setInterval(() => {
      setSecondsAgo(Math.floor((Date.now() - lastUpdated) / 1000))
    }, 1000)
    return () => clearInterval(t)
  }, [lastUpdated])

  return (
    <header className="top-header">
      <button className="icon-btn menu-btn" onClick={onMenuClick} title="Menu">☰</button>
      <div className="breadcrumb">
        <span className="breadcrumb-muted">Monitoring</span>
        <span className="breadcrumb-sep">/</span>
        <span>{VIEW_LABELS[view]}</span>
      </div>

      <div className="top-header-right">
        <span className="status-pill">
          <span className="status-dot" />
          Live · updated {secondsAgo}s ago
        </span>
        <span className="meta-text">{totalLogs} logs analyzed</span>
        <button className="icon-btn" onClick={onRefresh} title="Refresh now">
          ↻
        </button>
      </div>
    </header>
  )
}
