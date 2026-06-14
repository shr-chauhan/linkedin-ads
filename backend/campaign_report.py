from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta, timezone

import requests

import metrics_registry

BASE_URL = "https://api.linkedin.com/rest/"
API_VERSION = "202604"
TOP_COMPANIES_LIMIT = 20
TOP_FUNCTIONS_LIMIT = 20
TOP_SENIORITIES_LIMIT = 20
TOP_SIZES_LIMIT = 20
INCLUDE_VIRAL_METRICS = False


class TokenExpiredError(Exception):
    """Raised when LinkedIn rejects the access token (401/403)."""


def extract_id(value) -> str:
    if isinstance(value, dict):
        value = value.get("id", "")
    value = str(value)
    return value.split(":")[-1] if ":" in value else value


def format_timestamp(ms_timestamp) -> str:
    if not ms_timestamp:
        return None
    try:
        return datetime.fromtimestamp(int(ms_timestamp) / 1000.0, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        return None


def format_api_date(date_obj) -> str:
    if not date_obj:
        return None
    year = date_obj.get("year")
    month = date_obj.get("month")
    day = date_obj.get("day")
    if year and month and day:
        return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    return None


DEMO_RAW_FIELDS = [
    "impressions",
    "clicks",
    "landingPageClicks",
    "totalEngagements",
    "otherEngagements",
    "externalWebsiteConversions",
    "externalWebsitePostClickConversions",
    "externalWebsitePostViewConversions",
    "conversionValueInLocalCurrency",
    "likes",
    "reactions",
    "comments",
    "commentLikes",
    "shares",
    "follows",
    "companyPageClicks",
]


def build_demo_performance(row: dict) -> tuple[dict, dict]:
    """Build performance_raw/performance_calculated for a single MEMBER_* demographic row,
    mirroring the per-creative shape so the frontend can render them the same way."""
    raw_spend = row.get("costInLocalCurrency", 0)
    spend_float = round(float(raw_spend), 2) if raw_spend else 0.0

    performance_raw = {name: row.get(name, 0) for name in DEMO_RAW_FIELDS}
    performance_raw["costInLocalCurrency"] = str(raw_spend)
    performance_raw["spend_float"] = spend_float
    performance_raw["reporting_period"] = {
        "start_date": format_api_date(row.get("dateRange", {}).get("start")),
        "end_date": format_api_date(row.get("dateRange", {}).get("end")),
    }

    performance_calculated = {"core": metrics_registry.derive_core(performance_raw)}
    performance_raw.pop("spend_float", None)

    return performance_raw, performance_calculated


def get_linkedin_raw(url: str, token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        print(f"  API Request Warning: Status {resp.status_code} returned on URL:\n  {url}")
        try:
            return {"_api_error_payload": resp.json(), "_api_status": resp.status_code}
        except Exception:
            return {"_api_error_text": resp.text[:1000], "_api_status": resp.status_code}
    return resp.json()


def fetch_targeting_translations(urn_list, token):
    if not urn_list:
        return {}

    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }

    translations = {}
    urns = sorted(set(u for u in urn_list if not u.startswith("urn:li:adTargetingFacet:")))
    batch_size = 20

    print(f"├── Resolving {len(urns)} targeting entities...")

    for i in range(0, len(urns), batch_size):
        batch = urns[i:i + batch_size]
        encoded_urns = [urllib.parse.quote(urn, safe="") for urn in batch]
        urn_param = f"List({','.join(encoded_urns)})"

        lookup_url = (
            f"{BASE_URL}adTargetingEntities"
            f"?q=urns"
            f"&queryVersion=QUERY_USES_URNS"
            f"&urns={urn_param}"
        )

        resp = requests.get(lookup_url, headers=headers)
        if not resp.ok:
            print(f"Failed batch {i}-{i+len(batch)} status={resp.status_code}")
            continue

        payload = resp.json()
        for element in payload.get("elements", []):
            urn = element.get("urn")
            name = element.get("name")
            if urn and name:
                translations[urn] = name

    print(f"├── Successfully resolved {len(translations)} entities")
    return translations


def augment_targeting_criteria(item, translations: dict):
    if isinstance(item, list):
        new_list = []
        for element in item:
            if isinstance(element, str):
                if element in translations:
                    new_list.append({"urn": element, "resolved_name": translations[element]})
                elif "urn:li:organization:" in element:
                    new_list.append({"urn": element, "resolved_name": "Aisepedia (Excluded Corporate Page Node)"})
                else:
                    new_list.append(element)
            else:
                new_list.append(augment_targeting_criteria(element, translations))
        return new_list

    if isinstance(item, dict):
        new_dict = {}
        for key, value in item.items():
            if isinstance(key, str) and ("urn:li:adTargetingFacet:" in key or "urn:li:skill:" in key) and isinstance(value, list):
                processed_list = []
                for entry in value:
                    if isinstance(entry, str) and entry in translations:
                        processed_list.append({"urn": entry, "resolved_name": translations[entry]})
                    elif isinstance(entry, str) and "urn:li:organization:" in entry:
                        processed_list.append({"urn": entry, "resolved_name": "Aisepedia (Excluded Corporate Page Node)"})
                    else:
                        processed_list.append(entry)
                new_dict[key] = processed_list
            else:
                new_dict[key] = augment_targeting_criteria(value, translations)
        return new_dict

    return item


def extract_all_urns_from_targeting(criteria_dict: dict) -> list:
    urns = []
    if isinstance(criteria_dict, dict):
        for key, val in criteria_dict.items():
            if "urn:li:" in key:
                urns.append(key)
            urns.extend(extract_all_urns_from_targeting(val))
    elif isinstance(criteria_dict, list):
        for item in criteria_dict:
            urns.extend(extract_all_urns_from_targeting(item))
    elif isinstance(criteria_dict, str) and "urn:li:" in criteria_dict:
        urns.append(criteria_dict)
    return urns


def build_campaign_report(account_id: str, campaign_id: str, token: str) -> dict:
    print(f"🚀 Initializing deep raw metadata inspection for Campaign: {campaign_id}...")

    campaign_urn_string = f"urn:li:sponsoredCampaign:{campaign_id}"

    campaign_urn_encoded = urllib.parse.quote(campaign_urn_string, safe="")
    account_urn_encoded = urllib.parse.quote(f"urn:li:sponsoredAccount:{account_id}", safe="")

    # --- 1. Fetch Core Campaign Data ---
    print(f"├── Querying direct entity mapping path at /adAccounts/{account_id}/adCampaigns/{campaign_id}...")
    direct_camp_url = f"{BASE_URL}adAccounts/{account_id}/adCampaigns/{campaign_id}"
    campaign_direct_data = get_linkedin_raw(direct_camp_url, token)

    if campaign_direct_data.get("_api_status") in (401, 403):
        raise TokenExpiredError("LinkedIn API rejected the access token")

    # --- 2. Resolve Campaign Group Name ---
    campaign_group_urn = campaign_direct_data.get("campaignGroup")
    campaign_group_name = "Unknown Group"
    if campaign_group_urn:
        group_id = extract_id(campaign_group_urn)
        print(f"├── Resolving Campaign Group details for ID: {group_id}...")
        group_url = f"{BASE_URL}adAccounts/{account_id}/adCampaignGroups/{group_id}"
        group_data = get_linkedin_raw(group_url, token)
        campaign_group_name = group_data.get("name", "Unknown Group")

    # --- 3. Handle Targeting Transformations Upfront ---
    targeting_root = campaign_direct_data.get("targetingCriteria", {})
    all_extracted_urns = extract_all_urns_from_targeting(targeting_root)

    if all_extracted_urns:
        dictionary_mappings = fetch_targeting_translations(all_extracted_urns, token)
        augmented_targeting = augment_targeting_criteria(targeting_root, dictionary_mappings)
    else:
        augmented_targeting = targeting_root

    # --- 4. Resolve Associated Entity Name (Organization) ---
    associated_entity_urn = campaign_direct_data.get("associatedEntity")
    associated_entity_payload = None

    if associated_entity_urn:
        print(f"├── Resolving Campaign Associated Entity: {associated_entity_urn}...")
        entity_resolved = fetch_targeting_translations([associated_entity_urn], token)
        resolved_name = entity_resolved.get(associated_entity_urn)

        if not resolved_name and "urn:li:organization:" in associated_entity_urn:
            resolved_name = "Aisepedia"

        associated_entity_payload = {
            "urn": associated_entity_urn,
            "resolved_name": resolved_name or "Unknown Entity Reference"
        }

    # --- 5. Format Scheduling & Cost Data ---
    run_schedule = campaign_direct_data.get("runSchedule", {})
    start_date = format_timestamp(run_schedule.get("start"))
    end_date = format_timestamp(run_schedule.get("end"))

    daily_budget_raw = campaign_direct_data.get("dailyBudget", {})
    unit_cost_raw = campaign_direct_data.get("unitCost", {})

    output_payload = {
        "campaign": {
            "campaign_id": campaign_id,
            "campaign_name": campaign_direct_data.get("name"),
            "status": campaign_direct_data.get("status"),
            "campaign_group": {
                "urn": campaign_group_urn,
                "name": campaign_group_name
            },
            "objective_type": campaign_direct_data.get("objectiveType"),
            "optimization_target_type": campaign_direct_data.get("optimizationTargetType"),
            "cost_type": campaign_direct_data.get("costType"),
            "associated_entity": associated_entity_payload,
            "start_date": start_date,
            "end_date": end_date,
            "daily_budget": {
                "amount": float(daily_budget_raw.get("amount", 0)) if daily_budget_raw.get("amount") else 0.0,
                "currency": daily_budget_raw.get("currencyCode")
            },
            "unit_cost": {
                "amount": float(unit_cost_raw.get("amount", 0)) if unit_cost_raw.get("amount") else 0.0,
                "currency": unit_cost_raw.get("currencyCode")
            },
            "targeting": augmented_targeting,
            "creatives": [],
            "company_demographics": [],
            "job_function_demographics": [],
            "seniority_demographics": [],
            "company_size_demographics": []
        }
    }

    # --- 6. Fetch Child Creatives ---
    print("├── Crawling for all associated child creatives...")
    creatives_url = (
        f"{BASE_URL}adAccounts/{account_id}/creatives"
        f"?q=criteria"
        f"&campaigns=List({campaign_urn_encoded})"
    )
    creatives_data = get_linkedin_raw(creatives_url, token)
    creative_elements = creatives_data.get("elements", []) if isinstance(creatives_data, dict) else []

    # --- 6b. Pre-Pass: Resolve Post Content & Classify Each Creative ---
    print("├── Pre-pass: resolving post content and classifying creative format/objective...")
    creative_context = {}
    for creative in creative_elements:
        creative_urn = creative.get("id", "")
        creative_id = extract_id(creative_urn)

        content_block = creative.get("content", {})
        post_urn = content_block.get("reference") or content_block.get("post")
        post_data = {}
        post_content = {}

        if post_urn and "urn:li:event:" in post_urn:
            # Event creatives reference an urn:li:event:, which /posts/{id} cannot resolve.
            post_content = {"_reference_urn": post_urn}
        elif post_urn:
            post_key = urllib.parse.quote(post_urn, safe="") if any(x in post_urn for x in ["share:", "ugcPost:"]) else extract_id(post_urn)
            post_endpoint_url = f"{BASE_URL}posts/{post_key}"
            raw_post = get_linkedin_raw(post_endpoint_url, token)

            image_urn = None
            image_url = None
            content_details = raw_post.get("content", {})

            if "article" in content_details:
                image_urn = content_details["article"].get("thumbnail")
            elif "mediaComponent" in content_details:
                image_urn = content_details["mediaComponent"].get("thumbnail")

            if image_urn:
                print(f"│   │   ├── Resolving back-end image asset location for: {image_urn}...")
                escaped_image_urn = image_urn.replace(":", "%3A")
                image_lookup_url = f"{BASE_URL}images/{escaped_image_urn}"
                raw_image_data = get_linkedin_raw(image_lookup_url, token)
                image_url = raw_image_data.get("downloadUrl")

            post_data = {
                "post_id": raw_post.get("id"),
                "publish_date": format_timestamp(raw_post.get("publishedAt")),
                "title": content_details.get("article", {}).get("title"),
                "commentary": raw_post.get("commentary"),
                "landing_page": raw_post.get("contentLandingPage"),
                "cta": raw_post.get("contentCallToActionLabel"),
                "asset_image": {
                    "urn": image_urn,
                    "download_url": image_url
                }
            }
            post_content = content_details

        classification = metrics_registry.classify_creative(post_content, campaign_direct_data)
        print(f"│   │   ├── Classified as format='{classification['format']}', objective='{classification['objective']}'")

        creative_context[creative_id] = {
            "creative_urn": creative_urn,
            "post_data": post_data,
            "format": classification["format"],
            "objective": classification["objective"],
        }

    # --- 7. Plan & Fetch Global Analytics Metrics via Content-Aware Query Planner ---
    print("├── Planning analytics queries from per-creative format/objective classification...")
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=1095)
    date_range_str = f"(start:(year:{start_dt.year},month:{start_dt.month},day:{start_dt.day}),end:(year:{end_dt.year},month:{end_dt.month},day:{end_dt.day}))"
    # TODO: approximateMemberReach / audiencePenetration are only valid over a
    # <=92-day date range. If either metric is added to metrics_registry, query
    # it with its own short-window dateRange instead of the 1095-day
    # date_range_str used here.

    unique_format_objectives = {(ctx["format"], ctx["objective"]) for ctx in creative_context.values()}

    creative_field_union = set()
    for fmt, objective in unique_format_objectives:
        for plan in metrics_registry.plan_queries(fmt, objective, API_VERSION, INCLUDE_VIRAL_METRICS):
            if plan.pivot == metrics_registry.PIVOT_CREATIVE:
                creative_field_union.update(plan.fields)

    chunk_results = []
    for chunk in metrics_registry.chunk_fields(sorted(creative_field_union)):
        fields_param = ",".join(chunk)
        stats_url = (
            f"{BASE_URL}adAnalytics?q=analytics&pivot=CREATIVE&timeGranularity=ALL"
            f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={fields_param}"
        )
        chunk_results.append(get_linkedin_raw(stats_url, token).get("elements", []))

    performance_map = metrics_registry.merge_pivot_rows(chunk_results, extract_id)

    # --- 8. Assemble Hierarchical Creative Blocks ---
    DEEP_PIVOT_BREAKDOWN_KEYS = {
        metrics_registry.PIVOT_CARD_INDEX: "card_index_breakdown",
        metrics_registry.PIVOT_CONVERSATION_NODE: "conversation_node_breakdown",
        metrics_registry.PIVOT_SERVING_LOCATION: "serving_location_breakdown",
        metrics_registry.PIVOT_EVENT_STAGE: "event_stage_breakdown",
    }

    for creative in creative_elements:
        creative_urn = creative.get("id", "")
        creative_id = extract_id(creative_urn)
        print(f"│   ├── Processing Child Tree Context for Creative: {creative_id}...")

        ctx = creative_context.get(creative_id, {})
        post_data = ctx.get("post_data", {})
        fmt = ctx.get("format", "single_image")
        objective = ctx.get("objective", "engagement")
        applied_buckets = metrics_registry.applicable_buckets(fmt, objective)

        selected_metrics = metrics_registry.select_metrics(fmt, objective, API_VERSION, INCLUDE_VIRAL_METRICS)
        creative_field_names = [m.name for m in selected_metrics if metrics_registry.PIVOT_CREATIVE in m.pivots]

        perf_row = performance_map.get(creative_id, {})

        raw_spend = perf_row.get("costInLocalCurrency", 0)
        spend_float = round(float(raw_spend), 2) if raw_spend else 0.0

        # Core payload built dynamically from the metrics selected for this creative's format/objective
        performance_raw = {name: perf_row.get(name, 0) for name in creative_field_names}
        performance_raw["costInLocalCurrency"] = str(raw_spend)
        performance_raw["spend_float"] = spend_float  # Pass inside cleanly to fuel calculations
        performance_raw["currency_code"] = output_payload["campaign"]["daily_budget"]["currency"]
        performance_raw["reporting_period"] = {
            "start_date": format_api_date(perf_row.get("dateRange", {}).get("start")),
            "end_date": format_api_date(perf_row.get("dateRange", {}).get("end"))
        }
        performance_raw["pivot_creative_urn"] = perf_row.get("pivotValues", [None])[0]

        if metrics_registry.BUCKET_VIDEO in applied_buckets:
            performance_raw["data_freshness_note"] = (
                "videoWatchTime and averageVideoWatchTime may be delayed up to 48 hours."
            )

        # Deep-pivot creative-scoped breakdowns (CARD_INDEX / CONVERSATION_NODE / SERVING_LOCATION / EVENT_STAGE)
        breakdowns = {}
        creative_urn_encoded = urllib.parse.quote(creative_urn, safe="")
        for plan in metrics_registry.plan_queries(fmt, objective, API_VERSION, INCLUDE_VIRAL_METRICS):
            if not plan.creative_scoped:
                continue
            breakdown_key = DEEP_PIVOT_BREAKDOWN_KEYS.get(plan.pivot)
            if not breakdown_key:
                continue

            deep_rows = []
            for chunk in plan.chunks:
                fields_param = ",".join(chunk)
                deep_url = (
                    f"{BASE_URL}adAnalytics?q=analytics&pivot={plan.pivot}&timeGranularity=ALL"
                    f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})"
                    f"&creatives=List({creative_urn_encoded})&fields={fields_param}"
                )
                deep_rows.extend(get_linkedin_raw(deep_url, token).get("elements", []))
            breakdowns[breakdown_key] = deep_rows

        # Calculate ratios and downstream metrics, bucketed by content type
        performance_calculated = metrics_registry.calculate_metrics(performance_raw, applied_buckets)

        # Pop calculation helper keys out of the raw dict before outputting
        performance_raw.pop("spend_float", None)

        output_creative = {
            "creative_id": creative_id,
            "creative_name": creative.get("name"),
            "created_date": format_timestamp(creative.get("createdAt")),
            "modified_date": format_timestamp(creative.get("lastModifiedAt")),
            "post": post_data,
            "classification": {"format": fmt, "objective": objective},
            "performance_raw": performance_raw,
            "performance_calculated": performance_calculated
        }
        output_creative.update(breakdowns)

        output_payload["campaign"]["creatives"].append(output_creative)

    # --- Demographic Metrics ---
    # Guardrail: MEMBER_* pivots do NOT support approximateMemberReach, cardClicks/
    # cardImpressions, viralCardClicks/viralCardImpressions, or any other
    # non-demographic-pivot metric (see metrics_registry.py) -- those fields are
    # invalid under MEMBER_* pivots and will 400 the whole call. The full
    # common_spine + sc_engagement set below (DEMO_RAW_FIELDS) was verified live
    # against all four MEMBER_* pivots and works.
    demo_metrics = "dateRange,pivotValues," + ",".join(DEMO_RAW_FIELDS)

    # --- 9. Fetch Professional Demographics Breakdown by Member Company ---
    print("├── Querying Demographics Engine for Member Companies (pivot=MEMBER_COMPANY)...")
    demo_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=MEMBER_COMPANY&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={demo_metrics}"
    )
    company_analytics = get_linkedin_raw(demo_url, token)

    all_companies = []
    for row in company_analytics.get("elements", []) if isinstance(company_analytics, dict) else []:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            company_urn = p_vals[0]
            performance_raw, performance_calculated = build_demo_performance(row)

            all_companies.append({
                "company_urn": company_urn,
                "company_id": extract_id(company_urn),
                "company_name": "Name Restricted / Hidden",
                "performance_raw": performance_raw,
                "performance_calculated": performance_calculated,
            })

    all_companies.sort(key=lambda x: x["performance_raw"]["impressions"], reverse=True)
    company_report = all_companies[:TOP_COMPANIES_LIMIT]
    company_urn_list = [entry["company_urn"] for entry in company_report]

    if company_urn_list:
        print(f"├── Limiting company resolution tree to the top {len(company_urn_list)} records...")
        company_names = fetch_targeting_translations(company_urn_list, token)
        for entry in company_report:
            if entry["company_urn"] in company_names:
                entry["company_name"] = company_names[entry["company_urn"]]

    output_payload["campaign"]["company_demographics"] = company_report

    # --- 10. Fetch Demographics Breakdown by Job Function ---
    print("├── Querying Demographics Engine for Job Functions (pivot=MEMBER_JOB_FUNCTION)...")
    func_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=MEMBER_JOB_FUNCTION&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={demo_metrics}"
    )
    func_analytics = get_linkedin_raw(func_url, token)
    func_elements = func_analytics.get("elements", []) if isinstance(func_analytics, dict) else []

    all_functions = []
    for row in func_elements:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            func_urn = p_vals[0]
            performance_raw, performance_calculated = build_demo_performance(row)

            all_functions.append({
                "function_urn": func_urn,
                "function_id": extract_id(func_urn),
                "function_name": "Unknown Function",
                "performance_raw": performance_raw,
                "performance_calculated": performance_calculated,
            })

    all_functions.sort(key=lambda x: x["performance_raw"]["impressions"], reverse=True)
    func_report = all_functions[:TOP_FUNCTIONS_LIMIT]
    func_urn_list = [entry["function_urn"] for entry in func_report]

    if func_urn_list:
        print(f"├── Resolving {len(func_urn_list)} professional job function entities...")
        func_names = fetch_targeting_translations(func_urn_list, token)
        for entry in func_report:
            if entry["function_urn"] in func_names:
                entry["function_name"] = func_names[entry["function_urn"]]

    output_payload["campaign"]["job_function_demographics"] = func_report
    print(f"│   └── Isolated top {len(func_report)} job function performance blocks.")

    # --- 11. Fetch Demographics Breakdown by Seniority ---
    print("├── Querying Demographics Engine for Member Seniority (pivot=MEMBER_SENIORITY)...")
    seniority_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=MEMBER_SENIORITY&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={demo_metrics}"
    )
    sen_analytics = get_linkedin_raw(seniority_url, token)
    sen_elements = sen_analytics.get("elements", []) if isinstance(sen_analytics, dict) else []

    all_seniorities = []
    for row in sen_elements:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            sen_urn = p_vals[0]
            performance_raw, performance_calculated = build_demo_performance(row)

            all_seniorities.append({
                "seniority_urn": sen_urn,
                "seniority_id": extract_id(sen_urn),
                "seniority_name": "Unknown Seniority",
                "performance_raw": performance_raw,
                "performance_calculated": performance_calculated,
            })

    all_seniorities.sort(key=lambda x: x["performance_raw"]["impressions"], reverse=True)
    sen_report = all_seniorities[:TOP_SENIORITIES_LIMIT]
    sen_urn_list = [entry["seniority_urn"] for entry in sen_report]

    if sen_urn_list:
        print(f"├── Resolving {len(sen_urn_list)} professional seniority entities...")
        sen_names = fetch_targeting_translations(sen_urn_list, token)
        for entry in sen_report:
            if entry["seniority_urn"] in sen_names:
                entry["seniority_name"] = sen_names[entry["seniority_urn"]]

    output_payload["campaign"]["seniority_demographics"] = sen_report
    print(f"│   └── Isolated top {len(sen_report)} seniority performance blocks.")

    # --- 12. Fetch Demographics Breakdown by Company Size ---
    print("├── Querying Demographics Engine for Company Sizes (pivot=MEMBER_COMPANY_SIZE)...")
    size_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=MEMBER_COMPANY_SIZE&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={demo_metrics}"
    )
    size_analytics = get_linkedin_raw(size_url, token)
    size_elements = size_analytics.get("elements", []) if isinstance(size_analytics, dict) else []

    all_sizes = []
    for row in size_elements:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            size_urn = p_vals[0]
            size_id = extract_id(size_urn)
            performance_raw, performance_calculated = build_demo_performance(row)

            all_sizes.append({
                "company_size_urn": size_urn,
                "company_size_id": size_id,
                "performance_raw": performance_raw,
                "performance_calculated": performance_calculated,
            })

    all_sizes.sort(key=lambda x: x["performance_raw"]["impressions"], reverse=True)
    size_report = all_sizes[:TOP_SIZES_LIMIT]

    output_payload["campaign"]["company_size_demographics"] = size_report
    print(f"│   └── Isolated top {len(size_report)} company size performance blocks.")

    return output_payload
