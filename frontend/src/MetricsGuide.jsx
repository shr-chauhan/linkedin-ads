const FORMAT_ROWS = [
  ['single_image', 'Single Image', 'A static image ad', 'Post has content.media with an urn:li:image: URN'],
  ['article_link', 'Article Link', 'A link share with a preview thumbnail', 'Post has content.article'],
  ['video', 'Video', 'A video ad', 'Post has content.media with an urn:li:video: URN'],
  ['document', 'Document', 'A document/PDF ad', 'Post has content.media with an urn:li:document: URN'],
  ['carousel', 'Carousel', 'A multi-card image carousel', 'Post has content.carousel or content.multiImage'],
  ['message', 'Message', 'Sponsored InMail / Conversation Ads', "Campaign type is SPONSORED_INMAILS"],
  ['event', 'Event', 'A LinkedIn Event promotion', 'Content reference is urn:li:event:...'],
  ['text', 'Text', 'A text-only ad', 'Campaign type is TEXT_AD'],
]

const OBJECTIVE_ROWS = [
  ['lead_gen', 'Lead Gen', 'LEAD_GENERATION'],
  ['jobs', 'Jobs', 'JOB_APPLICANT'],
  ['conversions', 'Conversions', 'WEBSITE_CONVERSION'],
  ['awareness', 'Awareness', 'BRAND_AWARENESS'],
  ['engagement', 'Engagement', 'ENGAGEMENT, CREATIVE_ENGAGEMENT, WEBSITE_VISIT, WEBSITE_TRAFFIC'],
  ['video_view', 'Video View', 'VIDEO_VIEW'],
  ['event_reg', 'Event Reg', 'forced for Event-format creatives, regardless of campaign objective'],
]

function FormatBadge({ label }) {
  return <span className="badge badge-format">{label}</span>
}

function ObjectiveBadge({ label }) {
  return <span className="badge badge-objective">{label}</span>
}

export default function MetricsGuide({ onClose }) {
  return (
    <div className="metrics-guide-overlay" onClick={onClose}>
      <div className="metrics-guide-modal" onClick={(e) => e.stopPropagation()}>
        <button className="metrics-guide-close" onClick={onClose} aria-label="Close">×</button>

        <h2>Creative Types &amp; Metrics Guide</h2>
        <p>
          Each creative card shows a different set of metrics depending on its <strong>format</strong>
          {' '}(the blue badge) and the campaign's <strong>objective</strong> (the grey badge).
          This guide explains what each badge means and which metrics come with it.
        </p>

        <h3>Creative format badges</h3>
        <table>
          <thead>
            <tr><th>Badge</th><th>What it is</th><th>How it's detected</th></tr>
          </thead>
          <tbody>
            {FORMAT_ROWS.map(([key, label, desc, detect]) => (
              <tr key={key}>
                <td><FormatBadge label={label} /></td>
                <td>{desc}</td>
                <td>{detect}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="metrics-guide-note">
          In this account today, every creative is either <em>Single Image</em>, <em>Article Link</em>, or
          {' '}<em>Video</em> — the other formats are supported but haven't appeared yet.
        </p>

        <h3>Objective badges</h3>
        <table>
          <thead>
            <tr><th>Badge</th><th>LinkedIn objective type</th></tr>
          </thead>
          <tbody>
            {OBJECTIVE_ROWS.map(([key, label, types]) => (
              <tr key={key}>
                <td><ObjectiveBadge label={label} /></td>
                <td>{types}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3>Metrics shown on every creative ("Raw metrics")</h3>
        <ul>
          <li><strong>Impressions</strong></li>
          <li><strong>Clicks</strong></li>
          <li><strong>Landing Page Clicks</strong></li>
          <li><strong>Total Engagements</strong> / <strong>Other Engagements</strong></li>
          <li><strong>External Website Conversions</strong> (plus post-click / post-view splits)</li>
          <li><strong>Conversion Value In Local Currency</strong></li>
          <li><strong>Cost In Local Currency</strong></li>
          <li><strong>Likes, Reactions, Comments, Comment Likes, Shares, Follows, Company Page Clicks</strong> (every format except Message)</li>
        </ul>

        <h3>Calculated metrics shown on every creative ("Core")</h3>
        <ul>
          <li><strong>CTR %</strong> = Clicks / Impressions</li>
          <li><strong>CPC</strong> = Spend / Clicks</li>
          <li><strong>CPM</strong> = Spend / Impressions × 1000</li>
          <li><strong>Conversion Rate %</strong> = Conversions / Landing Page Clicks</li>
          <li><strong>Cost Per Conversion</strong> = Spend / Conversions</li>
        </ul>

        <h3>Format-specific metrics (added on top of the common set)</h3>

        <h4><FormatBadge label="Video" /></h4>
        <ul>
          <li>Raw: Video Starts, Video Views, Full Screen Plays, quartile completions (25/50/75/100%), Video Watch Time, Average Video Watch Time</li>
          <li>Calculated: View Rate %, quartile drop-off curve, Completion Rate %, Avg Watch Time (seconds) — shown as a drop-off chart</li>
          <li className="metrics-guide-note">⚠️ Watch-time fields can be delayed up to 48 hours (a note appears on the card when relevant)</li>
        </ul>

        <h4><FormatBadge label="Document" /></h4>
        <ul>
          <li>Raw: Document quartile completions (25/50/75/100%), Download Clicks</li>
          <li>Calculated: quartile %s, Completion Rate %, Download Rate % — shown as a completion funnel chart</li>
        </ul>

        <h4><FormatBadge label="Carousel" /></h4>
        <ul>
          <li>Raw: Card Clicks, Card Impressions (account-wide)</li>
          <li>Plus a per-card breakdown table showing clicks/impressions for each carousel card</li>
        </ul>

        <h4><FormatBadge label="Message" /></h4>
        <ul>
          <li>Raw: Sends, Opens, Action Clicks, Ad Unit Clicks, Text URL Clicks, Headline Clicks, Headline Impressions, lead-mail metrics</li>
          <li>Plus a per-node breakdown table (Conversation Node breakdown)</li>
          <li>Sponsored Content engagement metrics (likes/shares/etc.) do not apply</li>
        </ul>

        <h4><FormatBadge label="Event" /></h4>
        <ul>
          <li>Raw: Event Views (over 15s/30s/2min), Event Watch Time, Average Event Watch Time variants, Cost Per Event View variants</li>
          <li>Plus a per-stage breakdown table (pre-live / live / post-live)</li>
          <li>Objective is always forced to Event Reg</li>
        </ul>

        <h3>Objective-specific metrics (added on top of format metrics)</h3>

        <h4><ObjectiveBadge label="Lead Gen" /></h4>
        <ul>
          <li>Raw: One-Click Lead Form Opens, One-Click Leads, Qualified Leads, Cost Per Qualified Lead, Valid Work Email Leads, Talent Leads, Appointments Scheduled</li>
          <li>Calculated: Form Completion Rate %, Cost Per Lead, Cost Per Qualified Lead</li>
        </ul>

        <h4><ObjectiveBadge label="Jobs" /></h4>
        <ul>
          <li>Raw: Job Applications, Job Apply Clicks, plus post-click/post-view splits of each</li>
        </ul>

        <h4><ObjectiveBadge label="Event Reg" /></h4>
        <ul>
          <li>Raw: Registrations, plus post-click/post-view splits</li>
        </ul>

        <h3>Demographic breakdowns</h3>
        <p>
          The Companies, Job Functions, Seniority, and Company Size sections show the
          <strong> same raw + calculated metric set</strong> as the creative cards above
          (filtered to whichever buckets apply to that creative's format/objective), so you can
          compare CTR, Cost Per Lead, etc. across audiences — not just impressions.
        </p>

        <h3>Viral metrics</h3>
        <p>
          When enabled, every Sponsored Content metric above also gets a "viral" twin (e.g.
          Viral Impressions, Viral Clicks) — these reflect engagement on organic reshares of
          the ad, separate from the paid delivery numbers.
        </p>
      </div>
    </div>
  )
}
