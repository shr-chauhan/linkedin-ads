export function Loading() {
  return (
    <div className="state-view state-loading">
      <div className="spinner" />
      <p>Fetching campaign report... cold caches can take 10-30s (many sequential API calls).</p>
    </div>
  )
}

export function TokenExpired() {
  return (
    <div className="state-view state-token-expired">
      <h2>Re-authentication needed</h2>
      <p>
        The LinkedIn access token in <code>linkedin_ads/token.json</code> is missing or has been
        rejected by the API. Run the OAuth script in <code>linkedin_ads/</code> to refresh it,
        then try again.
      </p>
    </div>
  )
}

export function ErrorState({ message }) {
  return (
    <div className="state-view state-error">
      <h2>Something went wrong</h2>
      <p>{message}</p>
    </div>
  )
}

export function EmptyState({ message }) {
  return (
    <div className="state-view state-empty">
      <p>{message}</p>
    </div>
  )
}
