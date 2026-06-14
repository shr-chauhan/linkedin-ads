const ACRONYMS = new Set(['ctr', 'cpc', 'cpm', 'cpa', 'cta', 'url', 'urn', 'id', 'cxo', 'vp'])

export function humanizeKey(key) {
  if (!key) return ''
  const withSpaces = String(key)
    .replace(/_/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')

  return withSpaces
    .split(' ')
    .filter(Boolean)
    .map((word) => {
      const lower = word.toLowerCase()
      if (lower === 'percent') return '%'
      if (ACRONYMS.has(lower)) return word.toUpperCase()
      return word.charAt(0).toUpperCase() + word.slice(1)
    })
    .join(' ')
}

export function formatNumber(value) {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (num === null || num === undefined || isNaN(num)) return '—'
  return new Intl.NumberFormat('en-US').format(Math.round(num))
}

export function formatCurrency(value, currency) {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (num === null || num === undefined || isNaN(num)) return '—'
  return `${currency || ''} ${num.toFixed(2)}`.trim()
}

export function formatDate(dateStr) {
  if (!dateStr) return '—'
  const iso = dateStr.endsWith('Z') ? dateStr : `${dateStr}Z`
  const d = new Date(iso)
  if (isNaN(d.getTime())) return dateStr
  return d.toLocaleString()
}

export function formatMetricValue(key, value, currency) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)

  const lower = key.toLowerCase()
  if (lower.endsWith('percent')) return `${value}%`
  if (lower.endsWith('seconds')) return `${value}s`
  if (lower.includes('cost') || lower.includes('currency') || lower.includes('spend') || lower === 'cpc' || lower === 'cpm') {
    return formatCurrency(value, currency)
  }
  if (typeof value === 'number') return formatNumber(value)
  if (typeof value === 'string' && value.trim() !== '' && !isNaN(value)) return formatNumber(value)
  return String(value)
}
