export default function Kpi({ label, value, delta, deltaLabel, tone = 'neutral' }) {
  const hasDelta = delta !== null && delta !== undefined && delta !== 0
  const deltaUp = delta > 0

  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-row">
        <span className={`kpi-value kpi-${tone}`}>{value}</span>
        {hasDelta && (
          <span className={`kpi-delta ${deltaUp ? 'kpi-delta-up' : 'kpi-delta-down'}`}>
            {deltaUp ? '↑' : '↓'} {Math.abs(delta)}
          </span>
        )}
      </div>
      {deltaLabel && <div className="kpi-sub">{deltaLabel}</div>}
    </div>
  )
}
