"""
Declarative metric registry for LinkedIn adAnalytics queries.

Three orthogonal axes decide which metrics apply to a given creative:

1. Creative FORMAT (video / document / carousel / single_image / article_link /
   text / message / event) -- decides which engagement-DEPTH metrics exist.
2. Campaign OBJECTIVE (lead_gen / conversions / jobs / event_reg / awareness /
   engagement / video_view) -- decides which OUTCOME metrics matter. Orthogonal
   to format: a video creative in a lead-gen campaign needs both buckets.
3. PIVOT -- some "deep" metrics require a different `pivot` value and therefore
   a separate query (CARD_INDEX for per-card carousel, CONVERSATION_NODE for
   message/conversation nodes, SERVING_LOCATION for on/off-site video,
   EVENT_STAGE for live-event stages).

`select_metrics()` resolves axes 1+2 (plus API-version gating) into a flat,
deduped metric list. `plan_queries()` further groups that list by axis 3 into
one QueryPlan per pivot, each pre-chunked to LinkedIn's <=18-field-per-call
limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# --- API version gating -----------------------------------------------------

ALWAYS_AVAILABLE = "202301"   # baseline for long-standing fields
EVENT_MIN_VERSION = "202601"  # eventViews/eventWatchTime/etc first appear in the 2026-01 schema

# --- Pivot names (LinkedIn adAnalytics `pivot` enum values used here) -------

PIVOT_CREATIVE = "CREATIVE"
PIVOT_CARD_INDEX = "CARD_INDEX"
PIVOT_CONVERSATION_NODE = "CONVERSATION_NODE"
PIVOT_SERVING_LOCATION = "SERVING_LOCATION"
PIVOT_EVENT_STAGE = "EVENT_STAGE"

# --- Bucket names -------------------------------------------------------------

BUCKET_COMMON_SPINE = "common_spine"
BUCKET_SC_ENGAGEMENT = "sc_engagement"
BUCKET_VIDEO = "video"
BUCKET_DOCUMENT = "document"
BUCKET_CAROUSEL = "carousel"
BUCKET_MESSAGE = "message"
BUCKET_EVENT = "event"
BUCKET_OBJ_LEAD_GEN = "objective_lead_gen"
BUCKET_OBJ_JOBS = "objective_jobs"
BUCKET_OBJ_EVENT_REG = "objective_event_reg"
BUCKET_VIRAL_MIRROR = "viral_mirror"


@dataclass(frozen=True)
class Metric:
    """One field from the LinkedIn adAnalytics schema and the rules for using it."""
    name: str
    buckets: frozenset[str]
    min_version: str = ALWAYS_AVAILABLE
    pivots: frozenset[str] = frozenset({PIVOT_CREATIVE})
    sponsored_content_only: bool = False


# --- The registry --------------------------------------------------------------

METRICS: list[Metric] = [
    # common_spine -- always present, every creative
    Metric("impressions", frozenset({BUCKET_COMMON_SPINE})),
    Metric("costInLocalCurrency", frozenset({BUCKET_COMMON_SPINE})),
    Metric("clicks", frozenset({BUCKET_COMMON_SPINE})),
    Metric("landingPageClicks", frozenset({BUCKET_COMMON_SPINE})),
    Metric("totalEngagements", frozenset({BUCKET_COMMON_SPINE})),
    Metric("otherEngagements", frozenset({BUCKET_COMMON_SPINE})),
    Metric("externalWebsiteConversions", frozenset({BUCKET_COMMON_SPINE})),
    Metric("externalWebsitePostClickConversions", frozenset({BUCKET_COMMON_SPINE})),
    Metric("externalWebsitePostViewConversions", frozenset({BUCKET_COMMON_SPINE})),
    # Non-demographic pivots only -- never request alongside MEMBER_* pivots.
    Metric("conversionValueInLocalCurrency", frozenset({BUCKET_COMMON_SPINE})),

    # sc_engagement -- Sponsored Content formats only
    Metric("likes", frozenset({BUCKET_SC_ENGAGEMENT}), sponsored_content_only=True),
    Metric("reactions", frozenset({BUCKET_SC_ENGAGEMENT}), sponsored_content_only=True),
    Metric("comments", frozenset({BUCKET_SC_ENGAGEMENT}), sponsored_content_only=True),
    Metric("commentLikes", frozenset({BUCKET_SC_ENGAGEMENT}), sponsored_content_only=True),
    Metric("shares", frozenset({BUCKET_SC_ENGAGEMENT}), sponsored_content_only=True),
    Metric("follows", frozenset({BUCKET_SC_ENGAGEMENT}), sponsored_content_only=True),
    Metric("companyPageClicks", frozenset({BUCKET_SC_ENGAGEMENT}), sponsored_content_only=True),

    # video -- engagement depth for video creatives. videoStarts/videoViews/
    # quartiles/fullScreenPlays can additionally be pivoted by SERVING_LOCATION
    # (on-site vs off-site playback).
    Metric("videoStarts", frozenset({BUCKET_VIDEO}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_SERVING_LOCATION})),
    Metric("videoViews", frozenset({BUCKET_VIDEO}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_SERVING_LOCATION})),
    Metric("videoFirstQuartileCompletions", frozenset({BUCKET_VIDEO}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_SERVING_LOCATION})),
    Metric("videoMidpointCompletions", frozenset({BUCKET_VIDEO}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_SERVING_LOCATION})),
    Metric("videoThirdQuartileCompletions", frozenset({BUCKET_VIDEO}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_SERVING_LOCATION})),
    Metric("videoCompletions", frozenset({BUCKET_VIDEO}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_SERVING_LOCATION})),
    Metric("fullScreenPlays", frozenset({BUCKET_VIDEO}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_SERVING_LOCATION})),
    # videoWatchTime/averageVideoWatchTime: CREATIVE only, may be delayed up to 48h (flagged in output).
    Metric("videoWatchTime", frozenset({BUCKET_VIDEO})),
    Metric("averageVideoWatchTime", frozenset({BUCKET_VIDEO})),

    # document -- completion funnel for document ads
    Metric("documentFirstQuartileCompletions", frozenset({BUCKET_DOCUMENT})),
    Metric("documentMidpointCompletions", frozenset({BUCKET_DOCUMENT})),
    Metric("documentThirdQuartileCompletions", frozenset({BUCKET_DOCUMENT})),
    Metric("documentCompletions", frozenset({BUCKET_DOCUMENT})),
    Metric("downloadClicks", frozenset({BUCKET_DOCUMENT})),

    # carousel -- aggregate at CREATIVE; per-card breakdown needs CARD_INDEX.
    # Non-demographic pivots only -- never request alongside MEMBER_* pivots.
    Metric("cardClicks", frozenset({BUCKET_CAROUSEL}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CARD_INDEX})),
    Metric("cardImpressions", frozenset({BUCKET_CAROUSEL}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CARD_INDEX})),

    # message -- Sponsored Messaging / Conversation ads; node-level detail needs CONVERSATION_NODE.
    Metric("sends", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),
    Metric("opens", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),
    Metric("actionClicks", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),
    Metric("adUnitClicks", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),
    Metric("textUrlClicks", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),
    Metric("leadGenerationMailInterestedClicks", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),
    Metric("leadGenerationMailContactInfoShares", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),
    Metric("headlineClicks", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),
    Metric("headlineImpressions", frozenset({BUCKET_MESSAGE}), pivots=frozenset({PIVOT_CREATIVE, PIVOT_CONVERSATION_NODE})),

    # event -- live LinkedIn Events. First available in the 202601 schema; EVENT_STAGE
    # pivot breaks results down by PRE_LIVE / LIVE / POST_LIVE.
    Metric("eventViews", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("eventViewsOver15Seconds", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("eventViewsOver30Seconds", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("eventViewsOver2Minutes", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("eventWatchTime", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("averageEventWatchTime", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("averageEventWatchTimeOver15Seconds", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("averageEventWatchTimeOver30Seconds", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("averageEventWatchTimeOver2Minutes", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("costPerEventView", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("costPerEventViewOver15Seconds", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("costPerEventViewOver30Seconds", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),
    Metric("costPerEventViewOver2Minutes", frozenset({BUCKET_EVENT}), min_version=EVENT_MIN_VERSION, pivots=frozenset({PIVOT_CREATIVE, PIVOT_EVENT_STAGE})),

    # objective_lead_gen -- LEAD_GENERATION campaigns
    Metric("oneClickLeadFormOpens", frozenset({BUCKET_OBJ_LEAD_GEN})),
    Metric("oneClickLeads", frozenset({BUCKET_OBJ_LEAD_GEN})),
    Metric("qualifiedLeads", frozenset({BUCKET_OBJ_LEAD_GEN})),
    Metric("costPerQualifiedLead", frozenset({BUCKET_OBJ_LEAD_GEN})),
    Metric("validWorkEmailLeads", frozenset({BUCKET_OBJ_LEAD_GEN})),
    Metric("talentLeads", frozenset({BUCKET_OBJ_LEAD_GEN})),
    # CRITICAL: 202605-only. Requesting this on an older API_VERSION 400s the whole call.
    Metric("appointmentsScheduled", frozenset({BUCKET_OBJ_LEAD_GEN}), min_version="202605"),

    # objective_jobs -- JOB_APPLICANT campaigns
    Metric("jobApplications", frozenset({BUCKET_OBJ_JOBS})),
    Metric("jobApplyClicks", frozenset({BUCKET_OBJ_JOBS})),
    Metric("postClickJobApplications", frozenset({BUCKET_OBJ_JOBS})),
    Metric("postViewJobApplications", frozenset({BUCKET_OBJ_JOBS})),
    Metric("postClickJobApplyClicks", frozenset({BUCKET_OBJ_JOBS})),
    Metric("postViewJobApplyClicks", frozenset({BUCKET_OBJ_JOBS})),

    # objective_event_reg -- event-registration outcomes (paired with BUCKET_EVENT format)
    Metric("registrations", frozenset({BUCKET_OBJ_EVENT_REG})),
    Metric("postClickRegistrations", frozenset({BUCKET_OBJ_EVENT_REG})),
    Metric("postViewRegistrations", frozenset({BUCKET_OBJ_EVENT_REG})),
]


# --- Viral mirrors -------------------------------------------------------------
# Maps a selected metric name to its documented viral twin. Only metrics with a
# viral counterpart are listed; e.g. videoWatchTime, costInLocalCurrency,
# conversionValueInLocalCurrency, qualifiedLeads and all event* metrics have none.
VIRAL_TWINS: dict[str, str] = {
    "impressions": "viralImpressions",
    "clicks": "viralClicks",
    "landingPageClicks": "viralLandingPageClicks",
    "totalEngagements": "viralTotalEngagements",
    "otherEngagements": "viralOtherEngagements",
    "externalWebsiteConversions": "viralExternalWebsiteConversions",
    "externalWebsitePostClickConversions": "viralExternalWebsitePostClickConversions",
    "externalWebsitePostViewConversions": "viralExternalWebsitePostViewConversions",
    "likes": "viralLikes",
    "reactions": "viralReactions",
    "comments": "viralComments",
    "commentLikes": "viralCommentLikes",
    "shares": "viralShares",
    "follows": "viralFollows",
    "companyPageClicks": "viralCompanyPageClicks",
    "videoStarts": "viralVideoStarts",
    "videoViews": "viralVideoViews",
    "videoFirstQuartileCompletions": "viralVideoFirstQuartileCompletions",
    "videoMidpointCompletions": "viralVideoMidpointCompletions",
    "videoThirdQuartileCompletions": "viralVideoThirdQuartileCompletions",
    "videoCompletions": "viralVideoCompletions",
    "fullScreenPlays": "viralFullScreenPlays",
    "documentFirstQuartileCompletions": "viralDocumentFirstQuartileCompletions",
    "documentMidpointCompletions": "viralDocumentMidpointCompletions",
    "documentThirdQuartileCompletions": "viralDocumentThirdQuartileCompletions",
    "documentCompletions": "viralDocumentCompletions",
    "downloadClicks": "viralDownloadClicks",
    "cardClicks": "viralCardClicks",
    "cardImpressions": "viralCardImpressions",
    "oneClickLeadFormOpens": "viralOneClickLeadFormOpens",
    "oneClickLeads": "viralOneClickLeads",
    "jobApplications": "viralJobApplications",
    "jobApplyClicks": "viralJobApplyClicks",
    "postClickJobApplications": "viralPostClickJobApplications",
    "postViewJobApplications": "viralPostViewJobApplications",
    "postClickJobApplyClicks": "viralPostClickJobApplyClicks",
    "postViewJobApplyClicks": "viralPostViewJobApplyClicks",
    "registrations": "viralRegistrations",
    "postClickRegistrations": "viralPostClickRegistrations",
    "postViewRegistrations": "viralPostViewRegistrations",
}


# --- Format / objective classification -----------------------------------------

FORMAT_BUCKETS: dict[str, frozenset[str]] = {
    "video": frozenset({BUCKET_VIDEO}),
    "document": frozenset({BUCKET_DOCUMENT}),
    "carousel": frozenset({BUCKET_CAROUSEL}),
    "single_image": frozenset(),
    "article_link": frozenset(),
    "text": frozenset(),
    "message": frozenset({BUCKET_MESSAGE}),
    "event": frozenset({BUCKET_EVENT}),
}

# Formats treated as "Sponsored Content" for sc_engagement / viral_mirror purposes.
SC_FORMATS = frozenset({"video", "document", "carousel", "single_image", "article_link", "text", "event"})

# Format -> the deep pivot that gives it a per-creative breakdown beyond CREATIVE.
DEEP_PIVOT_BY_FORMAT: dict[str, str] = {
    "carousel": PIVOT_CARD_INDEX,
    "message": PIVOT_CONVERSATION_NODE,
    "video": PIVOT_SERVING_LOCATION,
    "event": PIVOT_EVENT_STAGE,
}

# LinkedIn campaign `objectiveType` -> internal objective key.
OBJECTIVE_TYPE_MAP: dict[str, str] = {
    "LEAD_GENERATION": "lead_gen",
    "JOB_APPLICANT": "jobs",
    "WEBSITE_CONVERSION": "conversions",
    "BRAND_AWARENESS": "awareness",
    "ENGAGEMENT": "engagement",
    "CREATIVE_ENGAGEMENT": "engagement",
    "WEBSITE_VISIT": "engagement",
    "WEBSITE_TRAFFIC": "engagement",
    "VIDEO_VIEW": "video_view",
}

OBJECTIVE_BUCKETS: dict[str, frozenset[str]] = {
    "lead_gen": frozenset({BUCKET_OBJ_LEAD_GEN}),
    "jobs": frozenset({BUCKET_OBJ_JOBS}),
    "event_reg": frozenset({BUCKET_OBJ_EVENT_REG}),
    "conversions": frozenset(),
    "awareness": frozenset(),
    "engagement": frozenset(),
    "video_view": frozenset(),
}


def classify_creative(post_content: dict, campaign: dict) -> dict:
    """
    Classify a creative's {format, objective} from the linked post's `content`
    shape and the campaign's type/objectiveType. Defaults to single_image/
    engagement when signals are ambiguous.

    `post_content` is `raw_post.get("content", {})` for the creative's linked
    post, optionally with a `_reference_urn` key set to the creative's content
    reference URN -- used to detect event creatives, whose reference is a
    `urn:li:event:` and never resolves via /posts/{id}.
    """
    post_content = post_content or {}
    campaign_type = campaign.get("type", "")
    reference_urn = str(post_content.get("_reference_urn") or "")

    if campaign_type == "SPONSORED_INMAILS":
        fmt = "message"
    elif "urn:li:event:" in reference_urn:
        fmt = "event"
    elif campaign_type == "TEXT_AD":
        fmt = "text"
    elif "carousel" in post_content or "multiImage" in post_content:
        fmt = "carousel"
    elif "article" in post_content:
        fmt = "article_link"
    elif "media" in post_content:
        media_id = str((post_content.get("media") or {}).get("id", ""))
        if "urn:li:video:" in media_id:
            fmt = "video"
        elif "urn:li:document:" in media_id:
            fmt = "document"
        else:
            fmt = "single_image"
    else:
        fmt = "single_image"

    objective = OBJECTIVE_TYPE_MAP.get(campaign.get("objectiveType", ""), "engagement")
    if fmt == "event":
        # Event creatives drive registrations regardless of the campaign's
        # nominal objectiveType, so the outcome bucket is forced here.
        objective = "event_reg"

    return {"format": fmt, "objective": objective}


def applicable_buckets(fmt: str, objective: str) -> set[str]:
    """The union of metric buckets that apply to a creative with this {format, objective}."""
    buckets = {BUCKET_COMMON_SPINE}
    if fmt in SC_FORMATS:
        buckets.add(BUCKET_SC_ENGAGEMENT)
    buckets |= FORMAT_BUCKETS.get(fmt, frozenset())
    buckets |= OBJECTIVE_BUCKETS.get(objective, frozenset())
    return buckets


def select_metrics(fmt: str, objective: str, api_version: str, include_viral: bool = False) -> list[Metric]:
    """
    Resolve axes 1+2 into a flat, deduped, version-filtered metric list.

    Filters out:
      - metrics whose bucket doesn't apply to this format/objective
      - metrics whose min_version > api_version (would 400 the whole call)
      - sponsored_content_only metrics when fmt isn't a Sponsored Content format
    """
    buckets = applicable_buckets(fmt, objective)
    is_sc = fmt in SC_FORMATS

    selected: list[Metric] = []
    seen: set[str] = set()
    for metric in METRICS:
        if not (metric.buckets & buckets):
            continue
        if metric.min_version > api_version:
            continue
        if metric.sponsored_content_only and not is_sc:
            continue
        if metric.name not in seen:
            seen.add(metric.name)
            selected.append(metric)

    if include_viral and is_sc:
        for source_name, viral_name in VIRAL_TWINS.items():
            if source_name in seen and viral_name not in seen:
                seen.add(viral_name)
                selected.append(Metric(
                    name=viral_name,
                    buckets=frozenset({BUCKET_VIRAL_MIRROR}),
                    min_version=ALWAYS_AVAILABLE,
                    pivots=frozenset({PIVOT_CREATIVE}),
                    sponsored_content_only=True,
                ))

    return selected


# --- Query planning & chunking ---------------------------------------------

MAX_FIELDS_PER_CHUNK = 18
STRUCTURAL_FIELDS = ["dateRange", "pivotValues"]


def chunk_fields(fields: list[str], max_fields: int = MAX_FIELDS_PER_CHUNK) -> list[list[str]]:
    """Split field names into <=max_fields chunks, each with dateRange+pivotValues appended."""
    unique_fields = list(dict.fromkeys(fields))
    return [
        unique_fields[i:i + max_fields] + STRUCTURAL_FIELDS
        for i in range(0, len(unique_fields), max_fields)
    ]


@dataclass(frozen=True)
class QueryPlan:
    """One adAnalytics query plan for a single pivot, pre-chunked to the field-count limit."""
    pivot: str
    fields: tuple[str, ...]
    chunks: tuple[tuple[str, ...], ...]
    creative_scoped: bool


def plan_queries(fmt: str, objective: str, api_version: str, include_viral: bool = False) -> list[QueryPlan]:
    """
    Build one QueryPlan per pivot needed for this {format, objective}:
      - always a CREATIVE-pivot plan (account-scoped, the primary query)
      - optionally a deep-pivot plan (CARD_INDEX/CONVERSATION_NODE/SERVING_LOCATION/
        EVENT_STAGE) when the format has per-creative "deep" metrics, scoped to a
        single creative via &creatives=List(<urn>)
    """
    metrics = select_metrics(fmt, objective, api_version, include_viral)
    plans: list[QueryPlan] = []

    creative_fields = tuple(m.name for m in metrics if PIVOT_CREATIVE in m.pivots)
    plans.append(QueryPlan(
        pivot=PIVOT_CREATIVE,
        fields=creative_fields,
        chunks=tuple(tuple(c) for c in chunk_fields(list(creative_fields))),
        creative_scoped=False,
    ))

    deep_pivot = DEEP_PIVOT_BY_FORMAT.get(fmt)
    if deep_pivot:
        deep_fields = tuple(m.name for m in metrics if deep_pivot in m.pivots)
        if deep_fields:
            plans.append(QueryPlan(
                pivot=deep_pivot,
                fields=deep_fields,
                chunks=tuple(tuple(c) for c in chunk_fields(list(deep_fields))),
                creative_scoped=True,
            ))

    return plans


def merge_pivot_rows(chunk_results, id_extractor) -> dict:
    """
    Merge rows from multiple chunked analytics responses, keyed by the entity id
    extracted from pivotValues[0] via `id_extractor` (e.g. inspect_campaign.extract_id).
    """
    merged: dict = {}
    for rows in chunk_results:
        for row in rows:
            p_vals = row.get("pivotValues", [])
            if not p_vals:
                continue
            key = id_extractor(p_vals[0])
            merged.setdefault(key, {}).update(row)
    return merged


# --- Bucketed derived metrics ------------------------------------------------

def _pct(numerator, denominator) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _ratio(numerator, denominator) -> float:
    return round(numerator / denominator, 2) if denominator else 0.0


def derive_core(raw: dict) -> dict:
    """ctr, cpc, cpm, conversion_rate, cost_per_conversion -- always computed."""
    impressions = raw.get("impressions", 0)
    clicks = raw.get("clicks", 0)
    landing_clicks = raw.get("landingPageClicks", 0)
    spend = raw.get("spend_float", 0.0)
    conversions = raw.get("externalWebsiteConversions", 0)
    return {
        "ctr_percent": _pct(clicks, impressions),
        "cpc": _ratio(spend, clicks),
        "cpm": round((spend / impressions) * 1000, 2) if impressions else 0.0,
        "conversion_rate_percent": _pct(conversions, landing_clicks),
        "cost_per_conversion": _ratio(spend, conversions),
    }


def derive_video(raw: dict) -> Optional[dict]:
    """view_rate, quartile drop-off curve, completion_rate, avg_watch_time -- only if video metrics present."""
    starts = raw.get("videoStarts", 0)
    views = raw.get("videoViews", 0)
    if not starts and not views:
        return None
    impressions = raw.get("impressions", 0)
    q1 = raw.get("videoFirstQuartileCompletions", 0)
    q2 = raw.get("videoMidpointCompletions", 0)
    q3 = raw.get("videoThirdQuartileCompletions", 0)
    q4 = raw.get("videoCompletions", 0)
    return {
        "view_rate_percent": _pct(views, impressions),
        "quartile_25_percent": _pct(q1, starts),
        "quartile_50_percent": _pct(q2, starts),
        "quartile_75_percent": _pct(q3, starts),
        "quartile_100_percent": _pct(q4, starts),
        "completion_rate_percent": _pct(q4, starts),
        "avg_watch_time_seconds": round(raw.get("averageVideoWatchTime", 0) / 1000, 2),
    }


def derive_document(raw: dict) -> Optional[dict]:
    """Completion funnel (25/50/75/100) and download_rate -- only if document metrics present."""
    impressions = raw.get("impressions", 0)
    q4 = raw.get("documentCompletions", 0)
    downloads = raw.get("downloadClicks", 0)
    if not impressions and not q4 and not downloads:
        return None
    q1 = raw.get("documentFirstQuartileCompletions", 0)
    q2 = raw.get("documentMidpointCompletions", 0)
    q3 = raw.get("documentThirdQuartileCompletions", 0)
    return {
        "quartile_25_percent": _pct(q1, impressions),
        "quartile_50_percent": _pct(q2, impressions),
        "quartile_75_percent": _pct(q3, impressions),
        "quartile_100_percent": _pct(q4, impressions),
        "completion_rate_percent": _pct(q4, impressions),
        "download_rate_percent": _pct(downloads, impressions),
    }


def derive_lead(raw: dict) -> Optional[dict]:
    """form_completion_rate, cost_per_lead, cost_per_qualified_lead -- only if lead metrics present."""
    form_opens = raw.get("oneClickLeadFormOpens", 0)
    leads = raw.get("oneClickLeads", 0)
    qualified_leads = raw.get("qualifiedLeads", 0)
    if not form_opens and not leads and not qualified_leads:
        return None
    spend = raw.get("spend_float", 0.0)
    return {
        "form_completion_rate_percent": _pct(leads, form_opens),
        "cost_per_lead": _ratio(spend, leads),
        "cost_per_qualified_lead": _ratio(spend, qualified_leads),
    }


def calculate_metrics(raw: dict, applied_buckets: set[str]) -> dict:
    """
    Per-bucket derived metrics. Always includes "core"; "video"/"document"/"lead"
    are attached only when their bucket applied AND their input metrics are present.
    """
    calc = {"core": derive_core(raw)}

    if BUCKET_VIDEO in applied_buckets:
        video = derive_video(raw)
        if video is not None:
            calc["video"] = video

    if BUCKET_DOCUMENT in applied_buckets:
        document = derive_document(raw)
        if document is not None:
            calc["document"] = document

    if BUCKET_OBJ_LEAD_GEN in applied_buckets:
        lead = derive_lead(raw)
        if lead is not None:
            calc["lead"] = lead

    return calc
