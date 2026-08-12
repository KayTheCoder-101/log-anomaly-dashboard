import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts'

function bucketByTenSeconds(logs) {
  const buckets = {}
  for (const log of logs) {
    const time = new Date(log.timestamp).getTime()
    const bucketTime = Math.floor(time / 10000) * 10000
    buckets[bucketTime] = (buckets[bucketTime] || 0) + 1
  }
  return Object.entries(buckets)
    .map(([time, count]) => ({ time: Number(time), count }))
    .sort((a, b) => a.time - b.time)
}

function groupByStatusClass(logs) {
  const groups = { '2xx': 0, '3xx': 0, '4xx': 0, '5xx': 0 }
  for (const log of logs) {
    const cls = `${String(log.status_code)[0]}xx`
    if (groups[cls] !== undefined) groups[cls]++
  }
  return Object.entries(groups).map(([name, count]) => ({ name, count }))
}

const STATUS_COLORS = {
  '2xx': '#3D9A6E',
  '3xx': '#4A7DBF',
  '4xx': '#C99A3E',
  '5xx': '#C85A4A',
}

export default function Charts({ logs }) {
  const volumeData = bucketByTenSeconds(logs)
  const statusData = groupByStatusClass(logs)

  return (
    <div className="charts">
      <div className="chart-panel">
        <h3>Log volume</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={volumeData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#5B8DEF" stopOpacity={0.22} />
                <stop offset="100%" stopColor="#5B8DEF" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="0" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis
              dataKey="time"
              tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              stroke="rgba(255,255,255,0.25)"
              tick={{ fill: '#6B7280', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              minTickGap={40}
            />
            <YAxis stroke="rgba(255,255,255,0.25)" tick={{ fill: '#6B7280', fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: '#181A20', border: '1px solid #2A2D36', borderRadius: 6, fontSize: 12 }}
              labelFormatter={(t) => new Date(t).toLocaleTimeString()}
            />
            <Area type="monotone" dataKey="count" stroke="#5B8DEF" strokeWidth={1.75} fill="url(#volumeFill)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-panel">
        <h3>Status class breakdown</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={statusData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }} barCategoryGap="24%">
            <CartesianGrid strokeDasharray="0" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="name" stroke="rgba(255,255,255,0.25)" tick={{ fill: '#6B7280', fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis stroke="rgba(255,255,255,0.25)" tick={{ fill: '#6B7280', fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: '#181A20', border: '1px solid #2A2D36', borderRadius: 6, fontSize: 12 }}
            />
            <Bar dataKey="count" radius={[3, 3, 0, 0]} maxBarSize={90} barSize={72}>
              {statusData.map((entry) => (
                <Cell key={entry.name} fill={STATUS_COLORS[entry.name]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
