function ModelPill({ log }) {
  const if_ = log.is_anomaly
  const lstm = log.lstm_is_anomaly
  if (!if_ && !lstm) return <span className="pill-none">—</span>
  if (if_ && lstm) return <span className="model-pill model-pill-strong">IF + LSTM</span>
  return <span className="model-pill">{if_ ? 'IF' : 'LSTM'}</span>
}

export function AnomalyFeed({ logs, onRowClick }) {
  const anomalies = logs
    .filter((log) => log.is_anomaly || log.lstm_is_anomaly)
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))

  return (
    <div className="panel">
      <h3>Live anomaly feed</h3>
      {anomalies.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No anomalies detected</div>
          <div className="empty-state-body">Your monitored logs are currently behaving normally.</div>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Source IP</th>
                <th>Request</th>
                <th>Status</th>
                <th className="num">Response</th>
                <th>Detection</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((log) => (
                <tr key={log.id} onClick={() => onRowClick(log)} tabIndex={0}>
                  <td className="mono">{new Date(log.timestamp).toLocaleTimeString()}</td>
                  <td className="mono">{log.source_ip}</td>
                  <td className="mono">{log.method} {log.endpoint}</td>
                  <td><span className={`status-chip status-${String(log.status_code)[0]}xx`}>{log.status_code}</span></td>
                  <td className="mono num">{log.response_time_ms ?? '—'} ms</td>
                  <td><ModelPill log={log} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function RecentLogs({ logs, onRowClick }) {
  return (
    <div className="panel">
      <h3>Recent logs</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Source IP</th>
              <th>Request</th>
              <th>Status</th>
              <th className="num">Response</th>
              <th>Detection</th>
            </tr>
          </thead>
          <tbody>
            {logs.slice(0, 100).map((log) => {
              const isAnomaly = log.is_anomaly || log.lstm_is_anomaly
              return (
                <tr
                  key={log.id}
                  className={isAnomaly ? 'row-anomaly' : 'row-normal'}
                  onClick={() => onRowClick(log)}
                  tabIndex={0}
                >
                  <td className="mono">{new Date(log.timestamp).toLocaleTimeString()}</td>
                  <td className="mono">{log.source_ip}</td>
                  <td className="mono">{log.method} {log.endpoint}</td>
                  <td><span className={`status-chip status-${String(log.status_code)[0]}xx`}>{log.status_code}</span></td>
                  <td className="mono num">{log.response_time_ms ?? '—'} ms</td>
                  <td><ModelPill log={log} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
