# Creative Types & Metrics Guide

This dashboard shows a different set of metrics for each creative depending on
its **format** (what the ad looks like) and the campaign's **objective** (what
the ad is optimized for). This doc explains what each badge means and which
metrics you'll see for it.

## Creative format badges

The blue badge on each creative card (`format`) is detected from the LinkedIn
post linked to the creative:

| Badge | What it is | How it's detected |
|---|---|---|
| **Single Image** | A static image ad | Post has `content.media` and the media URN is `urn:li:image:...` |
| **Article Link** | A link share with a preview thumbnail | Post has `content.article` |
| **Video** | A video ad | Post has `content.media` and the media URN is `urn:li:video:...` |
| **Document** | A document/carousel-PDF ad | Post has `content.media` and the media URN is `urn:li:document:...` |
| **Carousel** | A multi-card image carousel | Post has `content.carousel` or `content.multiImage` |
| **Message** | Sponsored InMail / Conversation Ads | Campaign type is `SPONSORED_INMAILS` |
| **Event** | A LinkedIn Event promotion | Creative's content reference is `urn:li:event:...` |
| **Text** | A text-only ad | Campaign type is `TEXT_AD` |

> In this account today, every creative is either **Single Image**, **Article
> Link**, or **Video** — the other formats are supported by the code but
> haven't appeared yet.

## Objective badges

The grey badge (`objective`) comes from the campaign's `objectiveType`:

| Badge | LinkedIn objective type |
|---|---|
| **Lead Gen** | `LEAD_GENERATION` |
| **Jobs** | `JOB_APPLICANT` |
| **Conversions** | `WEBSITE_CONVERSION` |
| **Awareness** | `BRAND_AWARENESS` |
| **Engagement** | `ENGAGEMENT`, `CREATIVE_ENGAGEMENT`, `WEBSITE_VISIT`, `WEBSITE_TRAFFIC` |
| **Video View** | `VIDEO_VIEW` |
| **Event Reg** | forced for **Event**-format creatives, regardless of campaign objective |

## Metrics shown on every creative ("Raw metrics")

These appear for **every** creative, no matter its format or objective:

- **Impressions**
- **Clicks**
- **Landing Page Clicks**
- **Total Engagements** / **Other Engagements**
- **External Website Conversions** (+ post-click / post-view splits)
- **Conversion Value In Local Currency**
- **Cost In Local Currency**
- **Likes, Reactions, Comments, Comment Likes, Shares, Follows, Company Page Clicks**
  (Sponsored Content engagement — shown for every format except Message)

## Calculated metrics shown on every creative ("Core")

Derived from the raw metrics above:

- **CTR %** = Clicks / Impressions
- **CPC** = Spend / Clicks
- **CPM** = Spend / Impressions × 1000
- **Conversion Rate %** = Conversions / Landing Page Clicks
- **Cost Per Conversion** = Spend / Conversions

## Format-specific metrics (added on top of the common set)

### Video
- Raw: **Video Starts, Video Views, Full Screen Plays**, quartile completions
  (**25/50/75/100%**), **Video Watch Time**, **Average Video Watch Time**
  - ⚠️ Watch-time fields can be delayed up to 48 hours (shown as a note on the card)
- Calculated ("video" bucket): **View Rate %**, quartile drop-off curve
  (25/50/75/100%), **Completion Rate %**, **Avg Watch Time (seconds)**
- Shown as a quartile drop-off chart

### Document
- Raw: **Document quartile completions** (25/50/75/100%), **Download Clicks**
- Calculated ("document" bucket): quartile %s, **Completion Rate %**,
  **Download Rate %**
- Shown as a completion funnel chart

### Carousel
- Raw: **Card Clicks, Card Impressions** (account-wide)
- Plus a **per-card breakdown table** (Card Index breakdown) showing
  clicks/impressions for each individual carousel card

### Message (Sponsored InMail / Conversation Ads)
- Raw: **Sends, Opens, Action Clicks, Ad Unit Clicks, Text URL Clicks,
  Headline Clicks, Headline Impressions**, lead-mail metrics
- Plus a **per-node breakdown table** (Conversation Node breakdown)
- Sponsored Content engagement metrics (likes/shares/etc.) do **not** apply

### Event
- Raw: **Event Views** (over 15s/30s/2min), **Event Watch Time**, **Average
  Event Watch Time** variants, **Cost Per Event View** variants
- Plus a **per-stage breakdown table** (Event Stage breakdown: pre-live /
  live / post-live)
- Objective is always forced to **Event Reg** (see below)

## Objective-specific metrics (added on top of format metrics)

### Lead Gen
- **One-Click Lead Form Opens, One-Click Leads, Qualified Leads, Cost Per
  Qualified Lead, Valid Work Email Leads, Talent Leads, Appointments Scheduled**
- Calculated ("lead" bucket): **Form Completion Rate %**, **Cost Per Lead**,
  **Cost Per Qualified Lead**

### Jobs
- **Job Applications, Job Apply Clicks**, plus post-click/post-view splits of each

### Event Reg
- **Registrations**, plus post-click/post-view splits

## Demographic breakdowns (Companies, Job Functions, Seniority, Company Size)

Each demographic row shows the **same raw + calculated metric set** as the
creative cards above (filtered to whichever buckets apply to that creative's
format/objective), so you can compare e.g. CTR or Cost Per Lead across
companies, not just impressions.

## Viral metrics (optional)

When enabled (`INCLUDE_VIRAL_METRICS`), every Sponsored Content metric above
also gets a "viral" twin (e.g. `viralImpressions`, `viralClicks`) — these
reflect engagement on **organic reshares** of the ad, separate from the paid
delivery numbers.
