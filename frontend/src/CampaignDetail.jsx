import { VideoQuartileChart, DocumentFunnelChart, LeadFunnelChart, DemographicsBarChart, DemographicsTable } from './Charts.jsx'
import MetricsGrid from './MetricsGrid.jsx'
import TargetingSection from './Targeting.jsx'
import { formatCurrency, formatDate, formatMetricValue, humanizeKey } from './format.js'

const RAW_META_FIELDS = ['currency_code', 'reporting_period', 'pivot_creative_urn', 'data_freshness_note']

const COMMON_SPINE_FIELDS = [
  'impressions',
  'clicks',
  'landingPageClicks',
  'totalEngagements',
  'otherEngagements',
  'externalWebsiteConversions',
  'externalWebsitePostClickConversions',
  'externalWebsitePostViewConversions',
  'conversionValueInLocalCurrency',
  'costInLocalCurrency',
  'likes',
  'reactions',
  'comments',
  'commentLikes',
  'shares',
  'follows',
  'companyPageClicks',
]

const BREAKDOWN_SECTIONS = [
  ['card_index_breakdown', 'Card index breakdown'],
  ['conversation_node_breakdown', 'Conversation node breakdown'],
  ['serving_location_breakdown', 'Serving location breakdown'],
  ['event_stage_breakdown', 'Event stage breakdown'],
]

function aggregateRaw(creatives) {
  const totals = {}
  for (const field of COMMON_SPINE_FIELDS) totals[field] = 0

  for (const creative of creatives) {
    const raw = creative.performance_raw || {}
    for (const field of COMMON_SPINE_FIELDS) {
      const v = raw[field]
      const num = typeof v === 'string' ? parseFloat(v) : v
      totals[field] += num || 0
    }
  }

  return totals
}

function deriveAggregateCore(totals) {
  const pct = (num, den) => (den ? Math.round((num / den) * 10000) / 100 : 0)
  const ratio = (num, den) => (den ? Math.round((num / den) * 100) / 100 : 0)

  return {
    ctr_percent: pct(totals.clicks, totals.impressions),
    cpc: ratio(totals.costInLocalCurrency, totals.clicks),
    cpm: totals.impressions ? Math.round((totals.costInLocalCurrency / totals.impressions) * 1000 * 100) / 100 : 0,
    conversion_rate_percent: pct(totals.externalWebsiteConversions, totals.landingPageClicks),
    cost_per_conversion: ratio(totals.costInLocalCurrency, totals.externalWebsiteConversions),
  }
}

function BreakdownTable({ title, rows, currency }) {
  const metricKeys = new Set()
  rows.forEach((row) => Object.keys(row).forEach((key) => {
    if (key !== 'pivotValues' && key !== 'dateRange') metricKeys.add(key)
  }))
  const keys = Array.from(metricKeys)

  return (
    <div className="creative-section">
      <h5>{title}</h5>
      <div className="breakdown-table-wrap">
        <table className="breakdown-table">
          <thead>
            <tr>
              <th>Pivot</th>
              {keys.map((key) => <th key={key}>{humanizeKey(key)}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>{(row.pivotValues || []).map((v) => String(v).split(':').pop()).join(', ')}</td>
                {keys.map((key) => <td key={key}>{formatMetricValue(key, row[key], currency)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function CreativeCard({ creative, currency }) {
  const raw = creative.performance_raw || {}
  const calc = creative.performance_calculated || {}
  const { format, objective } = creative.classification || {}
  const post = creative.post || {}
  const image = post.asset_image?.download_url

  return (
    <div className="creative-card">
      <div className="creative-header">
        <div>
          <h4>{creative.creative_name || `Creative ${creative.creative_id}`}</h4>
          <div className="creative-dates">
            <span>ID: {creative.creative_id}</span>
            {creative.created_date && <span>Created: {formatDate(creative.created_date)}</span>}
            {creative.modified_date && <span>Modified: {formatDate(creative.modified_date)}</span>}
            {post.publish_date && <span>Published: {formatDate(post.publish_date)}</span>}
          </div>
        </div>
        <span className="creative-format">{format} / {objective}</span>
      </div>

      {(image || post.commentary || post.title || post.landing_page) && (
        <div className="creative-post">
          {image && (
            <img className="creative-image" src={image} alt={post.title || creative.creative_name || ''} />
          )}
          <div className="creative-post-text">
            {post.title && <p className="creative-post-title">{post.title}</p>}
            {post.commentary && <p>{post.commentary}</p>}
            {post.landing_page && (
              <p className="creative-landing-page">
                <a href={post.landing_page} target="_blank" rel="noreferrer">{post.landing_page}</a>
              </p>
            )}
            {post.cta && <p className="creative-cta">CTA: {post.cta}</p>}
          </div>
        </div>
      )}

      <div className="creative-section">
        <h5>Raw metrics</h5>
        <MetricsGrid data={raw} currency={currency} exclude={RAW_META_FIELDS} />
        {raw.reporting_period && (
          <p className="reporting-period">
            Reporting period: {raw.reporting_period.start_date} to {raw.reporting_period.end_date}
          </p>
        )}
      </div>

      {Object.keys(calc).length > 0 && (
        <div className="creative-section calculated-section">
          <h5>Calculated metrics</h5>
          {Object.entries(calc).map(([bucket, values]) => (
            <div className="calc-bucket" key={bucket}>
              <h6>{humanizeKey(bucket)}</h6>
              <MetricsGrid data={values} currency={currency} />
              {bucket === 'video' && <VideoQuartileChart video={values} />}
              {bucket === 'document' && <DocumentFunnelChart document={values} />}
              {bucket === 'lead' && <LeadFunnelChart raw={raw} />}
              {bucket === 'video' && raw.data_freshness_note && (
                <p className="freshness-note">{raw.data_freshness_note}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {BREAKDOWN_SECTIONS.map(([key, title]) => (
        creative[key] && creative[key].length > 0 && (
          <BreakdownTable key={key} title={title} rows={creative[key]} currency={currency} />
        )
      ))}
    </div>
  )
}

export default function CampaignDetail({ report, onRefresh }) {
  const campaign = report.campaign
  const creatives = campaign.creatives || []
  const currency = campaign.daily_budget?.currency || campaign.unit_cost?.currency

  const rawTotals = aggregateRaw(creatives)
  const calcTotals = deriveAggregateCore(rawTotals)

  return (
    <div className="campaign-detail">
      <div className="campaign-header">
        <div className="campaign-header-top">
          <div>
            <h2>{campaign.campaign_name}</h2>
            <div className="campaign-meta">
              <span className={`status status-${(campaign.status || '').toLowerCase()}`}>
                {campaign.status}
              </span>
              <span>{campaign.objective_type}</span>
              <span>ID: {campaign.campaign_id}</span>
            </div>
          </div>
          <div className="campaign-refresh">
            <span className="fetched-at">
              Data fetched at {new Date(report.fetched_at).toLocaleString()}
            </span>
            <button onClick={onRefresh}>Refresh</button>
          </div>
        </div>

        <div className="creative-section">
          <h5>Campaign details</h5>
          <div className="metrics-grid">
            <div className="metric">
              <span className="metric-label">Campaign Group</span>
              <span className="metric-value">{campaign.campaign_group?.name || '—'}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Associated Entity</span>
              <span className="metric-value">{campaign.associated_entity?.resolved_name || '—'}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Optimization Target</span>
              <span className="metric-value">{campaign.optimization_target_type || '—'}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Cost Type</span>
              <span className="metric-value">{campaign.cost_type || '—'}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Daily Budget</span>
              <span className="metric-value">{formatCurrency(campaign.daily_budget?.amount, campaign.daily_budget?.currency)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Unit Cost</span>
              <span className="metric-value">{formatCurrency(campaign.unit_cost?.amount, campaign.unit_cost?.currency)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Start Date</span>
              <span className="metric-value">{formatDate(campaign.start_date)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">End Date</span>
              <span className="metric-value">{campaign.end_date ? formatDate(campaign.end_date) : '—'}</span>
            </div>
          </div>
        </div>

        <div className="creative-section">
          <h5>Aggregate raw metrics ({creatives.length} creative{creatives.length === 1 ? '' : 's'})</h5>
          <MetricsGrid data={rawTotals} currency={currency} />
        </div>

        <div className="creative-section">
          <h5>Aggregate calculated metrics</h5>
          <MetricsGrid data={calcTotals} currency={currency} />
        </div>
      </div>

      <TargetingSection targeting={campaign.targeting} />

      <section className="creatives">
        <h3>Creatives ({creatives.length})</h3>
        {creatives.map((creative) => (
          <CreativeCard key={creative.creative_id} creative={creative} currency={currency} />
        ))}
      </section>

      <section className="demographics">
        <h3>Demographics</h3>

        <div className="demo-section">
          <DemographicsBarChart
            data={campaign.company_demographics}
            nameKey="company_name"
            title="Top companies"
          />
          <DemographicsTable data={campaign.company_demographics} nameKey="company_name" currency={currency} />
        </div>

        <div className="demo-section">
          <DemographicsBarChart
            data={campaign.job_function_demographics}
            nameKey="function_name"
            title="Job functions"
          />
          <DemographicsTable data={campaign.job_function_demographics} nameKey="function_name" currency={currency} />
        </div>

        <div className="demo-section">
          <DemographicsBarChart
            data={campaign.seniority_demographics}
            nameKey="seniority_name"
            title="Seniority"
          />
          <DemographicsTable data={campaign.seniority_demographics} nameKey="seniority_name" currency={currency} />
        </div>

        <div className="demo-section">
          <DemographicsBarChart
            data={campaign.company_size_demographics}
            nameKey="company_size_id"
            title="Company size"
          />
          <DemographicsTable data={campaign.company_size_demographics} nameKey="company_size_id" currency={currency} />
        </div>
      </section>
    </div>
  )
}
