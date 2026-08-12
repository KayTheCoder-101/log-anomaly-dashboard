import { useState, useMemo, useRef, useCallback } from 'react'
import { useLogs } from './useLogs'
import Sidebar from './Sidebar'
import TopHeader from './TopHeader'
import Kpi from './Kpi'
import Charts from './Charts'
import { AnomalyFeed, RecentLogs } from './LogTables'
import Drawer from './Drawer'
import './App.css'

export default function App() {
  const { logs, loading, error } = useLogs(500)
  const [view, setView] = useState('overview')
  const [selectedLog, setSelectedLog] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(Date.now())

  const prevAnomalyCount = useRef(null)
  const [anomalyDelta, setAnomalyDelta] = useState(0)

  const statusOptions = useMemo(
    () => [...new Set(logs.map((l) => l.status_code))].sort((a, b) => a - b),
    [logs]
  )
  const endpointOptions = useMemo(
    () => [...new Set(logs.map((l) => l.endpoint))].sort(),
    [logs]
  )

  const [selectedStatuses, setSelectedStatuses] = useState([])
  const [selectedEndpoints, setSelectedEndpoints] = useState([])
  const [anomaliesOnly, setAnomaliesOnly] = useState(false)

  useMemo(() => {
    if (statusOptions.length && selectedStatuses.length === 0) setSelectedStatuses(statusOptions)
  }, [statusOptions])
  useMemo(() => {
    if (endpointOptions.length && selectedEndpoints.length === 0) setSelectedEndpoints(endpointOptions)
  }, [endpointOptions])

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      if (selectedStatuses.length && !selectedStatuses.includes(log.status_code)) return false
      if (selectedEndpoints.length && !selectedEndpoints.includes(log.endpoint)) return false
      if (anomaliesOnly && !(log.is_anomaly || log.lstm_is_anomaly)) return false
      return true
    })
  }, [logs, selectedStatuses, selectedEndpoints, anomaliesOnly])

  const total = filteredLogs.length
  const anomalyCount = filteredLogs.filter((l) => l.is_anomaly || l.lstm_is_anomaly).length
  const anomalyRate = total > 0 ? ((anomalyCount / total) * 100).toFixed(1) : '0.0'

  useMemo(() => {
    if (prevAnomalyCount.current !== null) {
      setAnomalyDelta(anomalyCount - prevAnomalyCount.current)
    }
    prevAnomalyCount.current = anomalyCount
    setLastUpdated(Date.now())
  }, [logs])

  const handleResetFilters = useCallback(() => {
    setSelectedStatuses(statusOptions)
    setSelectedEndpoints(endpointOptions)
    setAnomaliesOnly(false)
  }, [statusOptions, endpointOptions])

  if (loading && logs.length === 0) {
    return <div className="loading-state">Loading logs…</div>
  }
  if (error) {
    return <div className="error-state">Failed to load logs: {error}</div>
  }
  if (logs.length === 0) {
    return (
      <div className="empty-state-full">
        <div className="empty-state-title">No logs yet</div>
        <div className="empty-state-body">Start the generator to see live data here.</div>
      </div>
    )
  }

  return (
    <div className="app">
      {sidebarOpen && <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />}
      <Sidebar
        className={sidebarOpen ? 'sidebar-open' : ''}
        view={view}
        onViewChange={(v) => { setView(v); setSidebarOpen(false) }}
        statusOptions={statusOptions}
        selectedStatuses={selectedStatuses}
        onStatusChange={setSelectedStatuses}
        endpointOptions={endpointOptions}
        selectedEndpoints={selectedEndpoints}
        onEndpointChange={setSelectedEndpoints}
        anomaliesOnly={anomaliesOnly}
        onAnomaliesOnlyChange={setAnomaliesOnly}
        onResetFilters={handleResetFilters}
      />

      <div className="app-main">
        <TopHeader
          view={view}
          totalLogs={total}
          lastUpdated={lastUpdated}
          onRefresh={() => setLastUpdated(Date.now())}
          onMenuClick={() => setSidebarOpen(true)}
        />

        <main className="main-content">
          {(view === 'overview') && (
            <>
              <div className="kpi-row-grid">
                <Kpi label="Total logs" value={total} tone="neutral" />
                <Kpi
                  label="Anomalies"
                  value={anomalyCount}
                  delta={anomalyDelta}
                  deltaLabel="vs last refresh"
                  tone="critical"
                />
                <Kpi label="Anomaly rate" value={`${anomalyRate}%`} tone="warning" />
                <Kpi
                  label="System health"
                  value={Number(anomalyRate) > 40 ? 'Critical' : Number(anomalyRate) > 15 ? 'Warning' : 'Healthy'}
                  tone={Number(anomalyRate) > 40 ? 'critical' : Number(anomalyRate) > 15 ? 'warning' : 'healthy'}
                  deltaLabel="based on anomaly rate thresholds"
                />
              </div>
              <Charts logs={filteredLogs} />
              <AnomalyFeed logs={filteredLogs} onRowClick={setSelectedLog} />
              <RecentLogs logs={filteredLogs} onRowClick={setSelectedLog} />
            </>
          )}

          {view === 'live' && <RecentLogs logs={filteredLogs} onRowClick={setSelectedLog} />}

          {view === 'anomalies' && <AnomalyFeed logs={filteredLogs} onRowClick={setSelectedLog} />}

          {view === 'analytics' && (
            <>
              <Charts logs={filteredLogs} />
              <div className="panel">
                <h3>Detection model comparison</h3>
                <div className="model-stats">
                  <div>
                    <div className="model-stat-label">Isolation Forest flags</div>
                    <div className="model-stat-value">{filteredLogs.filter((l) => l.is_anomaly).length}</div>
                  </div>
                  <div>
                    <div className="model-stat-label">LSTM flags</div>
                    <div className="model-stat-value">{filteredLogs.filter((l) => l.lstm_is_anomaly).length}</div>
                  </div>
                  <div>
                    <div className="model-stat-label">Flagged by both</div>
                    <div className="model-stat-value">
                      {filteredLogs.filter((l) => l.is_anomaly && l.lstm_is_anomaly).length}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </main>
      </div>

      <Drawer log={selectedLog} onClose={() => setSelectedLog(null)} />
    </div>
  )
}
