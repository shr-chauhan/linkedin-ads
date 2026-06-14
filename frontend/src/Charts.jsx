import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { formatMetricValue, humanizeKey } from './format.js'

export function VideoQuartileChart({ video }) {
  const data = [
    { stage: 'Started', percent: 100 },
    { stage: '25%', percent: video.quartile_25_percent },
    { stage: '50%', percent: video.quartile_50_percent },
    { stage: '75%', percent: video.quartile_75_percent },
    { stage: '100%', percent: video.quartile_100_percent },
  ]

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="stage" />
        <YAxis unit="%" />
        <Tooltip formatter={(v) => `${v}%`} />
        <Bar dataKey="percent" fill="#0a66c2" />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function DocumentFunnelChart({ document }) {
  const data = [
    { stage: 'Viewed', percent: 100 },
    { stage: '25%', percent: document.quartile_25_percent },
    { stage: '50%', percent: document.quartile_50_percent },
    { stage: '75%', percent: document.quartile_75_percent },
    { stage: '100%', percent: document.quartile_100_percent },
  ]

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="stage" />
        <YAxis unit="%" />
        <Tooltip formatter={(v) => `${v}%`} />
        <Bar dataKey="percent" fill="#057642" />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function LeadFunnelChart({ raw }) {
  const data = [
    { stage: 'Form Opens', count: raw.oneClickLeadFormOpens || 0 },
    { stage: 'Leads', count: raw.oneClickLeads || 0 },
    { stage: 'Qualified Leads', count: raw.qualifiedLeads || 0 },
  ]

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" allowDecimals={false} />
        <YAxis type="category" dataKey="stage" width={110} />
        <Tooltip />
        <Bar dataKey="count" fill="#c37d16" />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function DemographicsBarChart({ data, nameKey, valueKey = 'impressions', title }) {
  if (!data || data.length === 0) {
    return (
      <div className="demo-chart">
        {title && <h4>{title}</h4>}
        <p className="demo-empty">No data</p>
      </div>
    )
  }

  const chartData = data.map((row) => ({
    name: String(row[nameKey]),
    value: row.performance_raw?.[valueKey] ?? row[valueKey],
  }))

  return (
    <div className="demo-chart">
      {title && <h4>{title}</h4>}
      <ResponsiveContainer width="100%" height={Math.max(120, chartData.length * 28)}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis type="category" dataKey="name" width={160} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="value" name={humanizeKey(valueKey)} fill="#0a66c2" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function DemographicsTable({ data, nameKey, currency }) {
  if (!data || data.length === 0) {
    return <p className="demo-empty">No data</p>
  }

  const rawKeys = []
  const rawKeySet = new Set()
  const coreKeys = []
  const coreKeySet = new Set()

  data.forEach((row) => {
    Object.keys(row.performance_raw || {}).forEach((key) => {
      if (key === 'reporting_period') return
      if (!rawKeySet.has(key)) {
        rawKeySet.add(key)
        rawKeys.push(key)
      }
    })
    Object.keys(row.performance_calculated?.core || {}).forEach((key) => {
      if (!coreKeySet.has(key)) {
        coreKeySet.add(key)
        coreKeys.push(key)
      }
    })
  })

  return (
    <div className="breakdown-table-wrap">
      <table className="breakdown-table">
        <thead>
          <tr>
            <th>{humanizeKey(nameKey)}</th>
            {rawKeys.map((key) => <th key={key}>{humanizeKey(key)}</th>)}
            {coreKeys.map((key) => <th key={`calc-${key}`}>{humanizeKey(key)}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i}>
              <td>{String(row[nameKey])}</td>
              {rawKeys.map((key) => (
                <td key={key}>{formatMetricValue(key, row.performance_raw?.[key], currency)}</td>
              ))}
              {coreKeys.map((key) => (
                <td key={`calc-${key}`}>{formatMetricValue(key, row.performance_calculated?.core?.[key], currency)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
