const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export async function fetchCampaigns() {
  const res = await fetch(`${API_BASE}/campaigns`)
  if (!res.ok) {
    throw new Error(`Failed to load campaigns (HTTP ${res.status})`)
  }
  return res.json()
}

export async function fetchCampaignReport(campaignId, { refresh = false } = {}) {
  const url = new URL(`${API_BASE}/campaigns/${campaignId}`, window.location.origin)
  if (refresh) {
    url.searchParams.set('refresh', 'true')
  }

  const res = await fetch(url)
  if (!res.ok) {
    let detail = null
    try {
      const body = await res.json()
      detail = body.detail ?? body
    } catch {
      // response had no JSON body
    }
    const error = new Error(`Failed to load campaign report (HTTP ${res.status})`)
    error.status = res.status
    error.detail = detail
    throw error
  }

  return res.json()
}
