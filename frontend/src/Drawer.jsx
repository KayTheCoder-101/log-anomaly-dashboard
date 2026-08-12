export default function Drawer({ log, onClose }) {
  if (!log) return null

  const flaggedBy = []
  if (log.is_anomaly) flaggedBy.push('Isolation Forest')
  if (log.lstm_is_anomaly) flaggedBy.push('LSTM Autoencoder')

  const severity = log.is_anomaly && log.lstm_is_anomaly ? 'High' : (flaggedBy.length ? 'Medium' : 'Normal')

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer">
        <div className="drawer-header">
          <span className="drawer-title">Log details</span>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        <div className="drawer-field">
          <label>Timestamp</label>
          <div className="mono">{new Date(log.timestamp).toLocaleString()}</div>
        </div>
        <div className="drawer-field">
          <label>Source IP</label>
          <div className="mono">{log.source_ip}</div>
        </div>
        <div className="drawer-field">
          <label>Request</label>
          <div className="mono">{log.method} {log.endpoint}</div>
        </div>
        <div className="drawer-field">
          <label>Status</label>
          <div className="mono">{log.status_code}</div>
        </div>
        <div className="drawer-field">
          <label>Response time</label>
          <div className="mono">{log.response_time_ms ?? '—'} ms</div>
        </div>
        <div className="drawer-field">
          <label>Bytes sent</label>
          <div className="mono">{log.bytes_sent ?? '—'}</div>
        </div>
        <div className="drawer-field">
          <label>Detection</label>
          <div>{flaggedBy.length ? flaggedBy.join(' + ') : 'Not flagged'}</div>
        </div>
        <div className="drawer-field">
          <label>Severity</label>
          <div className={`severity severity-${severity.toLowerCase()}`}>{severity}</div>
        </div>
        {log.anomaly_score != null && (
          <div className="drawer-field">
            <label>Isolation Forest score</label>
            <div className="mono">{Number(log.anomaly_score).toFixed(4)}</div>
          </div>
        )}
        {log.lstm_anomaly_score != null && (
          <div className="drawer-field">
            <label>LSTM reconstruction error</label>
            <div className="mono">{Number(log.lstm_anomaly_score).toFixed(4)}</div>
          </div>
        )}
      </aside>
    </>
  )
}
