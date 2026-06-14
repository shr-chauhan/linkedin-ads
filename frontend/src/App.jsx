import { useEffect, useState } from 'react'
import CampaignPicker from './CampaignPicker.jsx'
import CampaignDetail from './CampaignDetail.jsx'
import MetricsGuide from './MetricsGuide.jsx'
import { Loading, TokenExpired, ErrorState, EmptyState } from './StateViews.jsx'
import { fetchCampaigns, fetchCampaignReport } from './api.js'

export default function App() {
  const [campaigns, setCampaigns] = useState([])
  const [campaignsError, setCampaignsError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tokenExpired, setTokenExpired] = useState(false)
  const [showGuide, setShowGuide] = useState(false)

  useEffect(() => {
    fetchCampaigns()
      .then(setCampaigns)
      .catch((err) => setCampaignsError(err.message))
  }, [])

  function loadReport(campaignId, { refresh = false } = {}) {
    setLoading(true)
    setError(null)
    setTokenExpired(false)

    fetchCampaignReport(campaignId, { refresh })
      .then((data) => setReport(data))
      .catch((err) => {
        if (err.status === 401) {
          setTokenExpired(true)
        } else if (err.status === 404) {
          setError('Unknown campaign id.')
        } else {
          setError(err.detail?.message || err.message)
        }
      })
      .finally(() => setLoading(false))
  }

  function handleSelect(campaign) {
    setSelectedId(campaign.id)
    setReport(null)
    loadReport(campaign.id)
  }

  function handleRefresh() {
    if (selectedId) {
      loadReport(selectedId, { refresh: true })
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-top">
          <h1>LinkedIn Campaign Dashboard</h1>
          <button className="metrics-guide-trigger" onClick={() => setShowGuide(true)}>
            What am I looking at?
          </button>
        </div>
        <CampaignPicker
          campaigns={campaigns}
          campaignsError={campaignsError}
          selectedId={selectedId}
          onSelect={handleSelect}
        />
      </header>

      {showGuide && <MetricsGuide onClose={() => setShowGuide(false)} />}

      <main className="app-main">
        {!selectedId && <EmptyState message="Pick a campaign above to get started." />}
        {selectedId && loading && <Loading />}
        {selectedId && !loading && tokenExpired && <TokenExpired />}
        {selectedId && !loading && !tokenExpired && error && <ErrorState message={error} />}
        {selectedId && !loading && !tokenExpired && !error && report && (
          <CampaignDetail report={report} onRefresh={handleRefresh} />
        )}
      </main>
    </div>
  )
}
