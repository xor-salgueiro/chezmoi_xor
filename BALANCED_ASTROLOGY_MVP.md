# 1. Executive summary

This document defines a production-oriented **balanced MVP** for an evidence-based astrology application with:
- deterministic **Western astrology** natal + transit computation,
- structured interpretation with confidence and uncertainty handling,
- moderate, source-attributed historical/context retrieval,
- anti-hallucination controls that separate fact from interpretation and retrieved evidence.

The MVP is intentionally focused: one primary system (Western), one high-quality interpretation path, and one moderate retrieval layer. It avoids overreach (multi-system blending, pseudo-scientific causal claims, large research engines) while shipping a credible, extensible platform.

---

# 2. Product vision

Build a **trusted astrology intelligence app** that helps users understand:
1. Natal structure (placements, angles, houses, aspects, themes),
2. Time-bounded transits (today/tomorrow/week/month/year windows),
3. Important transit periods and stacked patterns,
4. Historical/biographical parallels with source traceability.

Core principle: every output claim belongs to one layer:
- **Calculated fact** (ephemeris, geometry, timing),
- **Astrological interpretation** (rule-based meaning),
- **Retrieved contextual evidence** (externally sourced parallels).

---

# 3. Scope and non-scope

## In MVP scope
- Western astrology as default and primary framework.
- Inputs: DOB, exact time, birthplace, optional current location, language, depth, orb/house preferences.
- Natal chart computation: planets/signs/houses, angles, major aspects, dominant themes.
- Transit computation for required windows: today, tomorrow, current week, next week, current month, next month, current year.
- Important transit detector: conjunction/opposition/square/trine/sextile, retrogrades, ingresses, house activations, lunations/eclipses, long cycles.
- Moderate retrieval layer with source quality ranking + match labels.
- Claim-level confidence and source attribution.
- Audit logs and user-facing transparency.

## Out of MVP scope
- Fully automated scientific causal inference engine.
- Multi-year personal journal/event learning loops.
- Massive historical knowledge graph ingestion.
- Full implementation of Vedic/Hellenistic/Chinese in same release.
- Autonomous LLM agentic pipelines without deterministic guardrails.

---

# 4. Recommended architecture

## Stack (pragmatic)
- **Frontend**: Next.js (TypeScript), SSR + client hydration.
- **Backend API**: FastAPI (Python) for astrology + retrieval orchestration.
- **Astro calculation service**: Swiss Ephemeris wrapper service (Python).
- **Async jobs**: Celery or RQ + Redis broker.
- **Database**: PostgreSQL.
- **Cache**: Redis (ephemeris snapshots, transit windows, retrieval snippets).
- **Search/Retrieval**: hybrid (Postgres FTS + vector index via pgvector).
- **Observability**: OpenTelemetry + structured logs + Prometheus/Grafana.

## Core services
1. **Identity/Profile Service**
   - stores profiles, consent, retention policy flags.
2. **Chart Service**
   - geocode/timezone normalize,
   - compute natal and transit facts.
3. **Interpretation Engine**
   - rule-based templates + weighted scoring,
   - LLM narrative synthesis only from structured payload.
4. **Retrieval Service**
   - pattern normalization,
   - source fetch/rank/filter,
   - evidence packaging + citations.
5. **Trust/Governance Service**
   - claim typing, confidence assignment,
   - unsupported-claim gating.

## Deployment
- Containerized services on Kubernetes or ECS.
- API gateway with rate limiting.
- Separate worker pool for retrieval-heavy jobs.

## Performance targets (MVP)
- Natal compute p95 < 1.2s.
- Transit compute (7 windows) p95 < 2.5s cached, < 5s uncached.
- Retrieval augmentation p95 < 6s (async progressive loading allowed).

## Tradeoffs
- Python backend simplifies astrology libraries and deterministic math; TypeScript-only backend would reduce stack diversity but raises implementation effort around ephemeris bindings.
- Moderate retrieval depth improves trust and latency; deep web crawling postponed.

---

# 5. Western astrology implementation

## Calculation assumptions
- Default: **Tropical zodiac**, Placidus houses (configurable).
- User-selectable house system (Placidus/Whole Sign/Equal in MVP).
- Orb defaults by aspect class (configurable in profile).

## Deterministic calculation pipeline
1. Parse and validate birth date/time.
2. Resolve birthplace -> lat/long.
3. Normalize timezone + DST -> UTC timestamp.
4. Compute natal planets + angles via Swiss Ephemeris.
5. Compute houses + major aspects.
6. Generate transit windows with exact hit times and applying/separating phase.

## Transit importance model (example)
`importance = base_aspect_weight + planet_weight + exactness_weight + angularity_weight + repetition/stack_weight + long_cycle_bonus`

Where:
- Aspect base weights: conjunction 1.0, opposition 0.9, square 0.85, trine 0.75, sextile 0.6.
- Planet weights: outer-to-personal and angle contacts weighted highest.
- Exactness based on orb distance and duration.

## Outputs
- Facts table + machine-usable JSON.
- Human interpretation blocks per time window.
- “Important transits” top-N ranked section with rationale.

---

# 6. Future support for other astrology systems

## Extensibility strategy
Define an `AstrologyFramework` interface:
- `compute_natal(input, config)`
- `compute_transits(input, timeframe, config)`
- `interpret(facts, style, locale)`
- `normalize_pattern(facts)` for retrieval compatibility

## Additional framework notes
- **Vedic/Jyotish**: requires sidereal ayanamsha, nakshatras, dasha logic.
- **Hellenistic**: sect, whole-sign default, zodiacal releasing (later phase).
- **Chinese**: different temporal ontology; separate calculation primitives and interpretive corpus.

## MVP policy
- Western enabled by default.
- Alternative frameworks behind feature flags.
- No blended interpretation in same report unless explicitly enabled and labeled.

---

# 7. Source and retrieval strategy

## Source tiers
1. Tier A: structured encyclopedic/public datasets, reputable archives.
2. Tier B: high-quality editorial biographies/timelines.
3. Tier C: astrology-domain datasets (clearly labeled).

## Retrieval flow
1. Convert major transit into normalized query pattern, e.g.:
   - `transit:Saturn square natal Sun`,
   - `window:YYYY-MM-DD..YYYY-MM-DD`,
   - `themes:career pressure/identity responsibility`.
2. Query indexed corpus + curated web connectors.
3. Re-rank by:
   - source reliability,
   - semantic relevance,
   - temporal alignment,
   - entity quality.
4. Label each match:
   - exact pattern match,
   - approximate match,
   - symbolic analogy,
   - insufficient evidence.
5. Keep only high-value top-K with citations.

## Quality gates
- Minimum citation fields: URL/source id, publication date (if known), extraction timestamp, confidence.
- No citation -> no evidence claim displayed.

---

# 8. Interpretation engine design

## Four-stage pipeline
1. **Fact assembly**: natal + transit deterministic outputs.
2. **Rule-based inference**: map configurations to domain themes.
3. **Scoring and uncertainty**: importance + confidence per claim.
4. **LLM synthesis**: produce readable text from structured facts only.

## LLM constraints
- Prompt receives only serialized fact graph and allowed glossary.
- Forbidden to invent events/research/sources.
- Must emit each statement with claim type and confidence.
- Post-generation verifier checks unsupported assertions.

## Reading styles
- concise / balanced / deep / expert
- same factual backbone; only narrative granularity changes.

---

# 9. Historical/context matching design

## Matching objects
- Transit signatures (planet, aspect, natal target, orb class).
- Time windows (exact, applying, separating period).
- Theme tags (e.g., relationship, career, health-stress, relocation).

## Matching algorithm (MVP)
- Rule-derived theme tags from transit signature.
- Retrieve candidate events/biographies with similar theme/time structures.
- Score = signature similarity + thematic overlap + source quality + recency balance.

## Output format per match
- match_type,
- reason_for_relevance,
- source metadata,
- confidence,
- caution note (“analogical, not causal proof”).

---

# 10. Anti-hallucination safeguards

1. **Typed claim model**: Fact / Interpretation / Retrieved Evidence.
2. **Schema validation** of all generated payloads.
3. **Citation-required policy** for evidence statements.
4. **No-memory facts**: LLM cannot originate planetary values.
5. **Unsupported-claim detector** before response release.
6. **Uncertainty language templates** for low-confidence items.
7. **Framework-bound prompts** (Western unless explicit override).
8. **Audit log** storing inputs, model versions, retrieval snapshots.

### Trust metrics
- Unsupported claim rate < 1.5% per 1,000 claims.
- Missing citation rate for evidence claims < 0.5%.
- Hallucination rate in red-team sets < 1.0%.

---

# 11. UX proposal

## Main screens
1. **Input Form**: birth data, location autocomplete, timezone confirmation.
2. **Natal Overview**: chart wheel + dominant themes + facts vs interpretation tabs.
3. **Transit Dashboard**: required seven windows as separate cards.
4. **Important Transits**: ranked list with timing and why-it-matters.
5. **Historical Parallels**: cited contextual cards with match-type label.
6. **Sources & Confidence**: per-claim trace panel.

## UX rules
- Always show badges: `Calculated Fact`, `Interpretation`, `Retrieved Evidence`.
- Expert mode exposes exact degree/orb and computation timestamps.
- Sensitive topics use guarded phrasing and non-deterministic framing.

---

# 12. Data model

## Key tables (PostgreSQL)
- `users(id, locale, created_at, ...)`
- `profiles(id, user_id, name_opt, birth_datetime_utc, birth_place_raw, lat, lon, tzid, consent_flags, retention_until)`
- `framework_configs(id, profile_id, framework, zodiac_mode, house_system, orb_profile)`
- `natal_charts(id, profile_id, framework, calc_version, chart_json, checksum, created_at)`
- `transit_runs(id, profile_id, window_type, start_ts, end_ts, calc_json, created_at)`
- `important_transits(id, transit_run_id, signature, importance_score, confidence, rationale_json)`
- `retrieval_queries(id, transit_id, query_json, executed_at)`
- `retrieval_results(id, query_id, source_tier, source_uri, title, snippet, match_type, relevance, evidence_confidence, metadata_json)`
- `readings(id, profile_id, window_type, style, output_json, model_version, verifier_report_json)`
- `audit_events(id, request_id, step, payload_hash, created_at)`

## Security/privacy
- PII encryption at rest for birth location and timestamps.
- Field-level access controls.
- TTL-based deletion jobs.

---

# 13. API design

## REST endpoints (MVP)
- `POST /v1/profiles`
- `POST /v1/charts/natal:compute`
- `POST /v1/transits:compute`
- `POST /v1/readings:generate`
- `POST /v1/readings:generate-all-windows`
- `POST /v1/retrieval:enrich`
- `GET /v1/readings/{id}`
- `GET /v1/readings/{id}/sources`
- `DELETE /v1/profiles/{id}`

## Example response contract (excerpt)
```json
{
  "window": "today",
  "claims": [
    {
      "type": "calculated_fact",
      "text": "Transiting Mars at 15° Leo squares natal Sun at 16° Taurus.",
      "confidence": 0.99
    },
    {
      "type": "interpretation",
      "text": "You may feel urgency around autonomy and visible action.",
      "confidence": 0.78
    },
    {
      "type": "retrieved_evidence",
      "text": "Comparable biography timeline example...",
      "confidence": 0.62,
      "sources": [{"uri": "...", "title": "..."}]
    }
  ]
}
```

---

# 14. MVP roadmap

## Phase 0 (2 weeks): foundations
- Domain schema, ephemeris integration, geocode/timezone normalization, test harness.

## Phase 1 (4 weeks): natal + transits
- Natal computation + seven-window transits + important transit ranking.
- API + basic UI with fact/interpretation separation.

## Phase 2 (3 weeks): interpretation + safeguards
- Rule-based interpretation library.
- LLM synthesis with verifier, confidence scoring.

## Phase 3 (3 weeks): retrieval enrichment
- Source connectors, ranking, match labels, citations UI.

## Phase 4 (2 weeks): hardening
- privacy controls, deletion workflows, observability, load/perf tuning.

Total MVP: ~14 weeks with 4–6 person team.

---

# 15. Risks and mitigations

1. **Perceived false certainty**
   - Mitigation: confidence + uncertainty language + layer labels.
2. **Hallucinated evidence**
   - Mitigation: citation-required gate and verifier.
3. **Latency spikes from retrieval**
   - Mitigation: async enrichment and cache warming.
4. **Incorrect timezone/geolocation**
   - Mitigation: explicit user confirmation + fallback prompts.
5. **Framework confusion**
   - Mitigation: hard framework tag in UI/API and no default blending.
6. **Sensitive interpretation harm**
   - Mitigation: safety style guide and escalation wording policy.

---

# 16. Testing and validation plan

## Deterministic correctness
- Ephemeris regression tests against trusted reference cases.
- Aspect detection/property tests for orb boundaries.
- Transit window edge tests around DST/UTC transitions.

## Retrieval quality
- Precision@K for top historical matches.
- Citation completeness audits.
- Source-tier distribution checks.

## Trust/safety validation
- Unsupported claim benchmark set.
- Hallucination red-team suite.
- Sensitive-content wording checks.

## MVP success metrics
- Chart calculation correctness >= 99.95% on reference fixtures.
- Transit detection correctness >= 99.5%.
- Source citation completeness >= 99% for evidence claims.
- Unsupported claim rate <= 1.5%.
- Retrieval precision@5 >= 0.70 on curated eval set.
- p95 end-to-end reading latency <= 8s (with enrichment).
- User trust indicator (self-reported transparency score) >= 4.2/5.

---

# 17. Example outputs

## A. Natal reading (shape)
```json
{
  "section": "natal",
  "facts": {
    "sun": "Taurus 16° in 10th house",
    "moon": "Aquarius 3° in 7th house",
    "angles": {"asc": "Leo 12°", "mc": "Taurus 20°"},
    "major_aspects": ["Sun square Moon", "Venus trine Jupiter"]
  },
  "interpretation": {
    "dominant_themes": ["visibility and craft", "autonomy vs collaboration"],
    "strengths": ["steady execution"],
    "tensions": ["fixed-sign rigidity"],
    "developmental_themes": ["flexibility under pressure"]
  },
  "confidence": 0.84
}
```

## B. Today / Tomorrow / Week / Month / Year (uniform shape)
```json
{
  "section": "today",
  "top_active_transits": [
    {
      "signature": "Mars square natal Sun",
      "timing": {"start": "2026-01-04", "peak": "2026-01-06", "end": "2026-01-09"},
      "importance": 0.88,
      "themes": ["assertion", "friction", "performance pressure"],
      "interpretation": "High-activation period; prioritize deliberate pacing.",
      "confidence": 0.79
    }
  ],
  "stacked_pattern_summary": "Mars + Saturn contacts indicate sustained demand on discipline.",
  "claim_layers": ["calculated_fact", "interpretation"]
}
```

Use identical payload shape for:
- `tomorrow`
- `current_week`
- `next_week`
- `current_month`
- `next_month`
- `current_year`

## C. Important transits
```json
{
  "section": "important_transits",
  "items": [
    {
      "signature": "Saturn conjunct natal MC",
      "why_it_matters": "Angular long-cycle transit affecting public role and accountability.",
      "term": "long_cycle",
      "reinforces_natal_theme": true,
      "importance": 0.93,
      "confidence": 0.86
    }
  ]
}
```

## D. Historical/context parallels
```json
{
  "section": "historical_context_parallels",
  "matches": [
    {
      "match_type": "approximate_pattern_match",
      "relevance_reason": "Comparable Saturn-MC period with documented career restructuring timeline.",
      "evidence_claim": "Biographical archive reports role transition within matching cycle window.",
      "confidence": 0.64,
      "sources": [
        {
          "title": "Example Archive Entry",
          "uri": "https://example.org/archive",
          "retrieved_at": "2026-01-06T11:12:00Z"
        }
      ],
      "caution": "Analogical context only; not causal proof."
    }
  ]
}
```

---

# 18. Final recommendation

Build in this order:
1. Deterministic Western chart/transit correctness,
2. Importance scoring and transparent claim-layered output,
3. Controlled LLM narrative synthesis,
4. Moderate retrieval with strict source gating,
5. Trust instrumentation (confidence, audits, deletion, observability).

Postpone until after MVP stability:
- Multi-framework production support,
- Deep correlation/causal analytics,
- Heavy personalized life-event learning,
- Large-scale crawling and graph expansion.

This sequence maximizes user trust and delivery probability while preserving a clean path to extensibility.
