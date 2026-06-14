import { useMemo, useState } from 'react'

export default function CampaignPicker({ campaigns, campaignsError, selectedId, onSelect }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return campaigns
    return campaigns.filter(
      (c) => c.name.toLowerCase().includes(q) || c.id.includes(q),
    )
  }, [campaigns, query])

  const selected = campaigns.find((c) => c.id === selectedId)

  if (campaignsError) {
    return (
      <div className="picker-error">
        Could not load campaigns.json: {campaignsError}
      </div>
    )
  }

  return (
    <div className="campaign-picker">
      <input
        type="text"
        placeholder="Search campaign by name or ID..."
        value={open ? query : (selected ? `${selected.name} (${selected.id})` : query)}
        onFocus={() => {
          setOpen(true)
          setQuery('')
        }}
        onBlur={() => setTimeout(() => setOpen(false), 100)}
        onChange={(e) => setQuery(e.target.value)}
      />
      {open && (
        <ul className="campaign-picker-list">
          {filtered.length === 0 && <li className="campaign-picker-empty">No matches</li>}
          {filtered.map((c) => (
            <li
              key={c.id}
              className={c.id === selectedId ? 'selected' : ''}
              onMouseDown={() => {
                onSelect(c)
                setOpen(false)
                setQuery('')
              }}
            >
              <span className="campaign-name">{c.name}</span>
              <span className="campaign-id">{c.id}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
