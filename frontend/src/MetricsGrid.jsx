import { formatMetricValue, humanizeKey } from './format.js'

export default function MetricsGrid({ data, currency, exclude = [] }) {
  if (!data) return null

  const entries = Object.entries(data).filter(([key]) => !exclude.includes(key))
  if (entries.length === 0) return <p className="demo-empty">No data</p>

  return (
    <div className="metrics-grid">
      {entries.map(([key, value]) => (
        <div className="metric" key={key}>
          <span className="metric-label">{humanizeKey(key)}</span>
          <span className="metric-value">{formatMetricValue(key, value, currency)}</span>
        </div>
      ))}
    </div>
  )
}
