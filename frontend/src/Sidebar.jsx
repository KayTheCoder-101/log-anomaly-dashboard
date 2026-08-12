const NAV_ITEMS = [
  { id: 'overview', label: 'Overview' },
  { id: 'live', label: 'Live Logs' },
  { id: 'anomalies', label: 'Anomalies' },
  { id: 'analytics', label: 'Analytics' },
]

export default function Sidebar({
  className = '',
  view,
  onViewChange,
  statusOptions,
  selectedStatuses,
  onStatusChange,
  endpointOptions,
  selectedEndpoints,
  onEndpointChange,
  anomaliesOnly,
  onAnomaliesOnlyChange,
  onResetFilters,
}) {
  function toggle(value, selected, onChange) {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value])
  }

  return (
    <aside className={`sidebar ${className}`}>
      <div className="brand">
        <div className="brand-mark" />
        <div>
          <div className="brand-name">LOGS</div>
          <div className="brand-sub">Anomaly Detection</div>
        </div>
      </div>

      <nav className="nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${view === item.id ? 'nav-item-active' : ''}`}
            onClick={() => onViewChange(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-divider" />

      <div className="filters">
        <div className="filters-heading">
          <span>Filters</span>
          <button className="reset-link" onClick={onResetFilters}>Reset</button>
        </div>

        <label className="checkbox-label checkbox-label-top">
          <input
            type="checkbox"
            checked={anomaliesOnly}
            onChange={(e) => onAnomaliesOnlyChange(e.target.checked)}
          />
          Anomalies only
        </label>

        <div className="filter-group">
          <label>Status code</label>
          <div className="chip-list">
            {statusOptions.map((status) => (
              <button
                key={status}
                className={`chip ${selectedStatuses.includes(status) ? 'chip-active' : ''}`}
                onClick={() => toggle(status, selectedStatuses, onStatusChange)}
              >
                {status}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-group">
          <label>Endpoint</label>
          <div className="chip-list">
            {endpointOptions.map((endpoint) => (
              <button
                key={endpoint}
                className={`chip ${selectedEndpoints.includes(endpoint) ? 'chip-active' : ''}`}
                onClick={() => toggle(endpoint, selectedEndpoints, onEndpointChange)}
              >
                {endpoint}
              </button>
            ))}
          </div>
        </div>

      </div>
          <div className="sidebar-footer">
        <span className="status-dot" />
        API connected
      </div>
    </aside>
  )
}
