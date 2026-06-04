# InterviewFindr — Design Spec

**Date:** 2026-06-03
**Status:** Draft, awaiting user review
**Author:** Brainstorming session (user + AI)

---

## 1. Context & Goals

### 1.1 Problem
Three family members are unemployed in a tough market and keep getting rejected across roles that should fit their experience. The user wants a tool that materially improves their odds by being **smarter about which jobs to apply to** and producing **tailored application materials**, not by mass-applying.

### 1.2 Family profiles

| Profile | Experience | Target field | Geography |
|---|---|---|---|
| Banker | 28 yrs | Commercial banking | US |
| Client partner | 30+ yrs | Tech consulting | US (open to UK) |
| MPH grad | 3 yrs | Public health | US |

These differ in seniority, domain vocabulary, ATS conventions, and which job sources matter (e.g., USAJobs is critical for the MPH grad, mostly irrelevant for the others).

### 1.3 Goals
- Deliver the top 25 most-likely-to-convert jobs per day per family member, not a firehose.
- Produce tailored resume + cover letter per surviving match, with all must-have keywords addressed.
- Auto-apply only to jobs posted on ATS systems with public, ToS-clean APIs (Greenhouse, Lever, Ashby). Provide assisted-apply kits for everything else.
- Learn from outcomes: refine matching weights per profile based on real response rates.
- Stay within ~$20-32/month in LLM costs for the whole family.

### 1.4 Non-goals
- We do **not** auto-apply via browser automation on LinkedIn, Indeed, or Glassdoor. ToS exposure is too high and the family account-ban risk is too severe.
- We do **not** promise a 100% interview rate. No system can. The honest claim is a 5-10x lift in interview rate per application at ~1/100th the volume of mass-applying.
- We do **not** build a general-purpose job board, a recruitment platform, or a multi-tenant SaaS. This is a personal tool for one family.
- We do **not** implement local LLMs (Ollama) on the VPS. Hostinger VPS is a small VM; all LLM inference goes to external providers.

---

## 2. High-Level Architecture

Self-hosted web application on the user's existing Hostinger VPS. Three layers.

```
┌──────────────────────────────────────────────────────────┐
│  Web UI (browser)                                        │
│  - Per-family-member login                               │
│  - Job feed, match details, tailoring preview            │
│  - Approve / edit / auto-apply / assisted-apply / skip   │
│  - Profile + resume + LLM settings                       │
│  - Application history + outcome tracking                │
└────────────────────────┬─────────────────────────────────┘
                         │  HTTPS (Caddy + Let's Encrypt)
┌────────────────────────▼─────────────────────────────────┐
│  Backend (FastAPI + APScheduler)                         │
│  - Auth (session cookies, role-based)                    │
│  - Profile manager (resume parse, LinkedIn import)        │
│  - Job fetcher  (per-source adapters, token-bucket)      │
│  - Matcher      (6-stage pipeline — see §7)              │
│  - Tailoring engine (LLM orchestration, escalating tier) │
│  - Apply engine (3 modes — see §8)                       │
│  - Outcome tracker (manual + ATS status polling)         │
│  - Object store interface (resume/cover letter PDFs)     │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│  Postgres  (jobs, matches, applications, profiles)        │
│  Object store (S3-compatible — MinIO bundled in Docker)  │
└──────────────────────────────────────────────────────────┘

                ┌─────────────────────────────┐
                │  External                    │
                │  - ATS APIs (T1)             │
                │  - Aggregator APIs (T2, T3)  │
                │  - OpenCode Zen / LLM APIs   │
                └─────────────────────────────┘
```

**Recommended stack:**
- Backend: Python 3.12 + FastAPI + SQLAlchemy 2.x + Alembic
- Frontend: HTMX + Tailwind + Alpine.js (server-rendered, minimal JS; can upgrade to React if complexity demands)
- DB: Postgres 16
- Object store: MinIO (S3-compatible, runs in same Docker compose)
- Reverse proxy: Caddy (auto-TLS)
- Scheduler: APScheduler in-process (start with); can move to dedicated worker if cron needs grow
- Container: Docker Compose
- ATS HTTP client: httpx (async)
- PDF generation: WeasyPrint (HTML→PDF) or Pandoc (Markdown→PDF) for tailored resumes

**Why Python:** Best LLM SDK coverage, best resume-parsing ecosystem (pdfplumber, python-docx), FastAPI is fast to build in. No JVM/JS deployment complexity.

**Why HTMX for the frontend:** The UI is mostly forms and lists. Server-rendered is faster to build and easier to deploy than a React SPA on a small VPS.

---

## 3. Data Model

Postgres schema (high-level; Alembic migrations will own the details).

```sql
-- Users (one row per family member + admin)
users (
  id            uuid pk,
  email         text unique not null,
  display_name  text not null,
  role          text not null,           -- 'admin' | 'member'
  password_hash text,                    -- argon2id; null until first login
  created_at    timestamptz default now()
)

-- Per-profile config (one row per user, the family-member's settings)
profiles (
  user_id              uuid pk references users(id),
  market_primary       text not null default 'US',
  market_secondary     text[] default '{}',
  resume_pdf_path      text,             -- object-store key for original
  resume_docx_path     text,
  resume_parsed_json    jsonb,           -- structured: skills, experience, education
  linkedin_raw_path    text,             -- optional raw import
  linkedin_parsed_json jsonb,
  preferences          jsonb,           -- { job_types, salary_min, salary_max,
                                         --   remote_ok, locations, exclude_companies,
                                         --   seniority_level, keywords_include,
                                         --   keywords_exclude }
  llm_default_provider text not null,    -- 'opencode_zen'
  llm_default_model    text not null,    -- 'kimi-k2.6'
  llm_escalation       jsonb,           -- { enabled, triggers, candidates,
                                         --   default_candidate, ab_test_rate }
  auto_apply_enabled   boolean default false,
  auto_apply_allowlist text[] default '{}',  -- ATS sources user has whitelisted
  tailoring_thresholds jsonb,           -- { min_match_score, max_per_day,
                                         --   jd_quality_min, must_have_coverage_min }
  created_at, updated_at
)

-- Raw job postings, deduplicated across fetches
jobs (
  id              uuid pk,
  source          text not null,        -- 'greenhouse' | 'lever' | 'ashby' | ...
  external_id     text not null,        -- source-specific job id
  url             text not null,
  company         text not null,
  title           text not null,
  location        text,
  remote_type     text,                 -- 'remote' | 'hybrid' | 'onsite' | null
  salary_min      numeric,
  salary_max      numeric,
  currency        text,
  description_html text,
  description_text text,                -- html-stripped plain text
  posted_at       timestamptz,
  raw_payload     jsonb,                -- full source response for debugging
  first_seen_at   timestamptz default now(),
  last_seen_at    timestamptz default now(),
  unique (source, external_id)
)

-- Match = the relationship between a user and a job, plus score and status
matches (
  id              uuid pk,
  user_id         uuid references users(id),
  job_id          uuid references jobs(id),
  match_score     numeric not null,     -- 0..1 probability-of-interview
  jd_quality      numeric,              -- 0..1
  seniority_match numeric,              -- 0..1
  must_have_cov   numeric,              -- 0..1
  comp_match      numeric,              -- 0..1
  reasoning       jsonb,                -- { strengths[], gaps[], notes }
  status          text not null,        -- 'new' | 'tailored' | 'approved' |
                                        --   'queued_apply' | 'applied' |
                                        --   'skipped' | 'rejected' | 'withdrawn'
  created_at, updated_at,
  unique (user_id, job_id)
)

-- Tailored artifacts (resume + cover letter) per match
tailored_artifacts (
  id                uuid pk,
  match_id          uuid references matches(id),
  resume_pdf_path   text,
  resume_docx_path  text,
  resume_text       text,                -- for ATS keyword validation
  resume_diff       jsonb,                -- what changed vs. original
  cover_letter_pdf  text,
  cover_letter_text text,
  skill_gap_notes   text,
  generated_at      timestamptz default now(),
  model_used        text,                -- 'kimi-k2.6' | 'deepseek-v4-pro' | ...
  prompt_version    text,                -- git-sha of prompt templates
  token_cost_usd    numeric,
  escalation_reason text                 -- 'user_marked_important' | null
)

-- Applications (audit trail)
applications (
  id                 uuid pk,
  match_id           uuid references matches(id),
  user_id            uuid references users(id),
  job_id             uuid references jobs(id),
  mode               text not null,      -- 'auto_api' | 'assisted' | 'manual_external'
  status             text not null,      -- 'queued' | 'submitted' |
                                         --   'acknowledged' | 'interview' |
                                         --   'rejected' | 'withdrawn' | 'no_response'
  submitted_at       timestamptz,
  external_ref       text,               -- ATS confirmation id, if any
  resume_snapshot    text,               -- object-store key for the PDF actually sent
  cover_letter_snap  text,
  user_outcome_note  text,
  outcome_updated_at timestamptz
)

-- Per-source adapter config (so we can add new sources without code changes
-- in the obvious places)
source_configs (
  source             text pk,            -- 'greenhouse', 'adzuna', 'jsearch', ...
  enabled            boolean default true,
  per_profile_overrides jsonb,           -- { user_id: { keywords, location, ... } }
  rate_limit         jsonb,              -- { calls_per_minute, daily_quota }
  api_key_env        text                -- env var name holding the API key
)

-- Outcome-feedback-derived weights (per profile, refreshed after enough data)
match_weight_overrides (
  user_id          uuid pk references users(id),
  weights          jsonb not null,      -- { w1: ..., w2: ..., ... }
  sample_size      int not null,        -- how many outcomes informed this
  computed_at      timestamptz default now()
)
```

**Why this shape:**
- `Match` separates "we found a job" from "we tailored for it" from "we applied." Cheap stages kill most jobs before we burn LLM tokens.
- `Application.resume_snapshot` snapshots the exact PDF sent so we can always answer "what did we actually submit?" without re-deriving.
- `source_configs` lives in the DB (not env vars) so we can enable/disable per source and per profile without redeploying.
- `match_weight_overrides` is the learning-loop output. Stage 4 starts with hand-tuned weights; this table replaces them after ~30 outcomes.

---

## 4. LLM Provider Layer

**Interface:**

```python
class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[dict],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> LLMResponse: ...

@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    raw: dict   # provider response for debugging
```

**Concrete providers (all behind the same interface):**

| Provider | Endpoint | Models we use |
|---|---|---|
| `AnthropicProvider` | `api.anthropic.com/v1/messages` | claude-sonnet-4.5 (escalation only) |
| `OpenAIProvider` | `api.openai.com/v1/chat/completions` | gpt-4o-mini, gpt-4o (escalation only) |
| `GitHubModelsProvider` | `models.github.ai` | gpt-4o-mini, etc. (fallback) |
| `OpenCodeZenProvider` | `opencode.ai/zen/go/v1/chat/completions` (OpenAI-compat) **and** `opencode.ai/zen/go/v1/messages` (Anthropic-compat) | kimi-k2.6, deepseek-v4-pro, glm-5.1, qwen3.7-max, qwen3.7-plus, qwen3.6-plus, mimo-v2.5, mimo-v2.5-pro, deepseek-v4-flash, minimax-m3, minimax-m2.7, minimax-m2.5 |

**Routing logic per LLM call:**
1. Always try the user's `llm_default_provider` + `llm_default_model` first.
2. On `triggers` (user-marked important, cover-letter specificity low, or A/B sample), switch to an escalation candidate.
3. On provider error (5xx, rate limit), fall back to a different provider in a configurable order.
4. Cache identical prompt+response pairs for 24h to avoid repeat cost (e.g., re-tailoring the same job for the same user on retry).

**Why OpenCode Zen is primary:**
- Single API key covers ~13 models across multiple vendors
- Both OpenAI-compatible and Anthropic-compatible endpoints
- We can route Anthropic-format model requests to `/v1/messages` and OpenAI-format to `/chat/completions` automatically based on the model family
- Per-token pricing is competitive; cheap-tier models like `kimi-k2.6` and `qwen3.6-plus` are very low cost

**Per-profile config example:**

```yaml
llm:
  default_provider: opencode_zen
  default_model: "kimi-k2.6"
  escalation:
    enabled: true
    triggers:
      - "user_marked_important"
      - "cover_letter_specificity_low"
    candidates:
      - "deepseek-v4-pro"
      - "glm-5.1"
      - "qwen3.7-max"
    default_candidate: "deepseek-v4-pro"
  ab_testing:
    enabled: true
    sample_rate: 0.05
  cache:
    enabled: true
    ttl_seconds: 86400
```

**Estimated cost per stage (3 profiles, top 25/day, ~50% pass Stages 1-3):**

| Stage | Per call | Calls/day (3 profiles) | Daily cost |
|---|---|---|---|
| 1: heuristic | $0 | 75+ | $0 |
| 2: parse (kimi-k2.6) | ~$0.0002 | ~75 | $0.015 |
| 3: skill match | $0 | ~75 | $0 |
| 4: probability | $0 | ~75 | $0 |
| 5: tailor default (kimi-k2.6) | ~$0.005 | ~68 | $0.34 |
| 5: tailor escalation (deepseek-v4-pro) | ~$0.04 | ~7 | $0.28 |
| 6: validate | $0 | ~75 | $0 |
| **Total** | | | **~$0.64/day, ~$20/month** |

---

## 5. Job Sources (US-Primary)

Four tiers, ordered by ToS cleanliness.

### 5.1 Tier 1 — Native ATS APIs (auto-apply capable)

| Source | Read API | Auto-apply API | Notes |
|---|---|---|---|
| **Greenhouse** | `boards-api.greenhouse.io/v1/boards/{token}/jobs` | `POST /v1/boards/{token}/jobs/{id}` (Basic Auth) | Thousands of companies; the most important Tier-1 source. Per-company `board_token` is public. |
| **Lever** | `api.lever.co/v0/postings/{site}?mode=json` | `POST /v0/postings/{site}/apply` (form-encoded) | Many tech companies. Site slug is public. |
| **Ashby** | `api.ashbyhq.com/posting-api/job-board/{jobBoardName}` | `POST /api/v1/applicationForm` (per-job applicationFormId) | Modern startups. |
| **Workday** | Per-tenant URL; most require customer-specific config | Not generally available | Opt-in per enterprise tenant; complex. Off by default. |
| **SmartRecruiters** | `api.smartrecruiters.com/v1/companies/{id}/postings` | None (read-only public API) | Useful for large enterprises. |
| **USAJOBS** | `data.usajobs.gov/api/search` (requires API key header) | None (manual apply only on usajobs.gov) | Critical for the MPH grad (federal public health roles). |

**All Tier-1 sources use official, public APIs with terms-of-service compliance. Auto-apply is supported only for Greenhouse, Lever, Ashby.**

### 5.2 Tier 2 — Aggregator/board APIs (read-only, ToS-clean)

| Source | API | Notes |
|---|---|---|
| **Adzuna** | `api.adzuna.com/v1/api/jobs/{country}/search/1` | Multi-country; `country=us` is the primary path. Paid tier needed for volume; free tier ~250 calls/month. |
| **The Muse** | `www.themuse.com/api/public/jobs` | US-focused, free tier. |
| **Remotive** | `remotive.com/api/remote-jobs` | Free, remote-only. |
| **Himalayas** | `himalayas.app/jobs/api` and `/jobs/api/search` | Free, no auth, filter by country/seniority. |
| **Remote OK** | `remoteok.com/api` | Free, public, 30K+ remote jobs. |
| **RemoteJobs.org** | `remotejobs.org/api/v1/jobs` | Free, no auth, multi-source. |
| **Career Nest** | `careernest.cloud/api/feed` | Free, no auth, 1.5M+ listings. |
| **Rise** | `api.joinrise.io/api/v1/jobs/public` | Free, requires attribution backlink. |
| **Remote First Jobs** | `remotefirstjobs.com/jobs-api` | Public JSON. |

### 5.3 Tier 3 — Indirect-exposure aggregators (user-approved with caveats)

These services scrape Google for Jobs, which aggregates from Indeed, LinkedIn, Glassdoor, ZipRecruiter, Monster. The data is the same we'd avoid scraping directly, accessed through a paid middleman. The user has explicitly approved this trade-off. Read-only, no apply.

| Source | API | Pricing | Notes |
|---|---|---|---|
| **JSearch (RapidAPI)** | `jsearch.p.rapidapi.com/search` | Free tier 250 calls/month, then $25/mo | Primary aggregator. Aggregates Indeed, LinkedIn, Glassdoor, ZipRecruiter, Monster. |
| **SerpApi Google Jobs** | `serpapi.com/search?engine=google_jobs` | $50/mo for 5K searches | Backstop if JSearch coverage is too thin. |

**Risk acknowledgment in the spec, not hidden:**
- If Indeed/LinkedIn change their ToS and pressure these aggregators, the source may break without notice.
- We do not auto-apply to any Tier-3 listing. The user submits via assisted-apply.

### 5.4 Tier 4 — Off-limits (do not integrate)

LinkedIn (direct), Indeed (direct), Glassdoor (direct), ZipRecruiter (direct), Naukri, Monster India, Shine. No scraping. No unofficial APIs. Period.

### 5.5 Per-profile source config

```yaml
# profiles.banker (commercial banking, 28 yrs)
sources:
  - { type: greenhouse, enabled: true }
  - { type: lever,      enabled: true }
  - { type: ashby,      enabled: true }
  - { type: workday,    enabled: false }    # opt-in per tenant later
  - { type: usajobs,    enabled: false }    # not relevant
  - { type: adzuna,     enabled: true, country: "us" }
  - { type: jsearch,    enabled: true, tier: "free" }
  - { type: himalayas,  enabled: false }    # remote-only, not a fit
  - { type: remoteok,   enabled: false }
  - { type: themuse,    enabled: true }

# profiles.consultant (tech consulting client partner, 30+ yrs)
sources:
  - { type: greenhouse, enabled: true }
  - { type: lever,      enabled: true }
  - { type: ashby,      enabled: true }
  - { type: usajobs,    enabled: false }
  - { type: adzuna,     enabled: true, country: "us" }
  - { type: jsearch,    enabled: true, tier: "free" }
  - { type: himalayas,  enabled: true }
  - { type: remoteok,   enabled: true }
  - { type: themuse,    enabled: true }

# profiles.mph (recent MPH grad, 3 yrs)
sources:
  - { type: greenhouse, enabled: true }     # NGOs / global health orgs
  - { type: lever,      enabled: true }
  - { type: ashby,      enabled: true }
  - { type: usajobs,    enabled: true }     # ★ primary path
  - { type: adzuna,     enabled: true, country: "us", keywords: ["public health", "epidemiology", "policy", "global health"] }
  - { type: jsearch,    enabled: true, tier: "free" }
  - { type: themuse,    enabled: true }
```

### 5.6 Rate limiting and politeness

- Per-source token-bucket (calls-per-minute) and daily-quota configured in `source_configs`.
- Adzuna free tier: 250 calls/month. We must budget carefully; cache aggressively.
- USAJobs: header-based auth, ~1000 requests/hour limit; we batch and cache.
- Greenhouse/Lever/Ashby: very generous limits (~10/sec). We use 1/sec to be polite.
- JSearch free tier: 250 calls/month. We use it for breadth only; per-profile, we use it 2x/day to pull the latest cross-board index.
- The fetcher runs every 6 hours for the high-throughput sources (Greenhouse, Lever, Ashby) and once daily for everything else.

---

## 6. Resume Parsing and Profile Ingestion

### 6.1 Inputs
- **Resume file:** PDF and/or DOCX upload via the web UI.
- **LinkedIn import:** Three options, in order of preference:
  1. Manual paste of LinkedIn profile export (the ZIP that LinkedIn provides under *Settings → Data Privacy → Get a copy of your data*).
  2. User pastes LinkedIn profile URL; we extract the public profile HTML.
  3. Manual: user fills structured fields in the UI.

### 6.2 Parsing
- **PDF resume:** `pdfplumber` for layout, `pdfminer.six` as fallback. Extract text, then LLM call to structure into a `resume_parsed_json` schema (see below).
- **DOCX resume:** `python-docx`. Same downstream LLM structuring.
- **LinkedIn export ZIP:** built-in JSON files; mostly pre-structured.
- **LinkedIn URL HTML:** `httpx` + `selectolax` or similar; LLM structures the result.

**Structured resume schema (`resume_parsed_json`):**
```json
{
  "summary": "...",
  "contact": { "name": "...", "email": "...", "phone": "...", "location": "..." },
  "experience": [
    {
      "company": "...",
      "title": "...",
      "start": "YYYY-MM",
      "end": "YYYY-MM" | "present",
      "location": "...",
      "bullets": ["..."]
    }
  ],
  "education": [{ "school": "...", "degree": "...", "field": "...", "year": ... }],
  "skills": [
    { "name": "Python", "years": 5, "context": "backend services" },
    { "name": "Treasury operations", "years": 12, "context": "commercial banking" }
  ],
  "certifications": [...],
  "languages": [...]
}
```

The skill graph is the **structured** representation: each skill carries years-of-experience and context (industry/role). This is what Stage 3 matches against.

### 6.3 Tailored output format
- **PDF:** WeasyPrint rendering an HTML template. Standard fonts (Helvetica/Arial), no tables for layout, no images. Selectable text.
- **DOCX:** `python-docx` (preserves editability in Word).
- **Per-market template variants:**
  - US: 1-page preferred for <10 yrs experience, 2 pages otherwise. No photo. No DOB.
  - UK: 2 pages. No photo (modern UK convention) but allowed.
  - EU: 2 pages. Photo sometimes expected. Will revisit if a profile explicitly targets EU.
- **Per-stage outputs are all rendered from a Jinja2 template** so changes to layout don't require code changes.

---

## 7. Matching + Tailoring Pipeline (6 Stages)

The pipeline runs per cron tick per profile. Most jobs die in the early stages; only the survivors get LLM tailoring.

### 7.1 Stage 1 — JD Quality Heuristic (deterministic, free)

Computes a 0-1 quality score from textual signals in the JD. Kills low-quality postings.

**Positive signals (+):** comp range listed, named team/manager, specific tech/tools named, "you will..." responsibility statements, "we offer..." benefits block, recent posting (<7 days), company has >50 employees (heuristic from description richness).

**Negative signals (−):** "rockstar/ninja/guru", "fast-paced environment", "wear many hats", no compensation, reposted 3+ times across sources, vague responsibilities, internal contradictions ("10 yrs experience required" + "entry level"), "must have" list with >12 items, "competitive salary" with no number, third-party recruiter posting with no client named.

**Output:** `jd_quality` ∈ [0,1]. Threshold: `0.40` (configurable per profile).

**Kills ~50-60% of incoming jobs.** No LLM call.

### 7.2 Stage 2 — Structured Parsing (cheap LLM, ~500 input + ~500 output tokens)

For jobs passing Stage 1, run a cheap LLM (default `kimi-k2.6`) to extract structured fields.

**Prompt asks for JSON with:**
```json
{
  "must_haves": ["3+ years Python", "PostgreSQL experience", ...],
  "nice_to_haves": [...],
  "compensation": { "min": ..., "max": ..., "currency": "USD", "period": "yearly" },
  "level": "IC3" | "IC4" | "manager" | "director" | "vp" | ...,
  "role_function": "engineering" | "product" | "design" | "operations" | ...,
  "team": "...",
  "employment_type": "full_time" | "contract" | "part_time" | ...,
  "remote_policy": "remote" | "hybrid" | "onsite",
  "years_experience_min": 3,
  "years_experience_max": null
}
```

**Validation:** parse JSON, fall back to re-prompt with stricter format hint on parse failure. After 2 failures, mark job as `parse_failed` and skip.

**Cost:** ~$0.0002/job at kimi-k2.6 pricing.

### 7.3 Stage 3 — Skill Graph Match (deterministic, free)

Compute coverage of `must_haves` against the user's `resume_parsed_json.skills`.

**Algorithm:**
1. For each must_have, search resume for direct match.
2. If no direct match, check "transferred skill" map: hand-curated equivalence table (e.g., "HubSpot" → partial-credit transfer to "Salesforce" with confidence 0.4).
3. Coverage = (sum of confidence scores) / must_haves.length.
4. If a must_have is uncovered, run a small LLM call (`kimi-k2.6`) to assess if a one-line cover-letter addition could plausibly close it. Output: `closable_in_letter: bool` per uncovered must-have.

**Output:** `must_have_cov` ∈ [0,1], plus `uncovered[]` with `closable_in_letter` flags.

**Threshold:** `0.70` (i.e., 70% of must-haves either directly matched or closeable). Kills ~20% of remaining jobs.

### 7.4 Stage 4 — Probability Score (composite, deterministic, free)

```python
prob = (
    w_match_coverage  * must_have_cov
  + w_jd_quality      * jd_quality
  + w_seniority_match * seniority_match
  + w_comp_match      * comp_match
  + w_recency         * recency_score
  + w_source_weight   * source_weight
  - w_competition     * competition_density  # if available
)
```

Initial weights (hand-tuned):
- `w_match_coverage = 0.30`
- `w_jd_quality = 0.20`
- `w_seniority_match = 0.20`
- `w_comp_match = 0.10`
- `w_recency = 0.10`
- `w_source_weight = 0.05`
- `w_competition = 0.05`

**`seniority_match`:** function of `(resume_level - job_level).abs()`. Perfect match = 1.0, 1 step off = 0.7, 2+ steps off = 0.3.

**`comp_match`:** 1.0 if comp_range overlaps user preference, 0.5 if comp not listed (benefit of doubt), 0.0 if comp explicitly below preference.

**`recency_score`:** 1.0 if <2 days, decaying linearly to 0.3 at 30 days.

**`source_weight`:** 1.0 for USAJobs and Greenhouse, 0.9 for Lever/Ashby, 0.8 for Adzuna, 0.6 for JSearch (less curated), 0.7 for Tier-2 free boards.

**`competition_density`:** optional, only available from some sources. 0.5 default.

**Threshold:** `0.40` (per user decision: balanced, not strict).

**Top-N selection:** sort surviving jobs by `prob` desc, take top 25 (configurable per profile).

### 7.5 Stage 5 — Tailoring (escalating LLM)

For each of the top-N surviving jobs:

**Step 5a: Resume tailoring**
- Input: original resume (structured JSON), parsed JD, must_have list, skill-gap notes.
- Output: tailored resume as both JSON and rendered PDF/DOCX.
- Prompt: instruct the model to **mirror must_have keywords verbatim where they don't misrepresent**, reorder bullets to emphasize relevant experience, and add specific quantified achievements from the candidate's history that match the role.
- **Constraint check (deterministic, after generation):** every must_have keyword string must appear at least once in the rendered resume text. If not, regenerate with explicit instruction to include the missing strings.

**Step 5b: Cover letter**
- Input: tailored resume JSON, parsed JD, company name, role title, team.
- Output: cover letter (PDF + text).
- Prompt: 3 paragraphs. (1) Specific opener referencing the company/role/team, not generic. (2) 2-3 concrete examples from the resume that map to must-haves, with quantification. (3) Specific closer about why this company/team, not boilerplate.
- **Constraint check:** cover letter must reference at least 2 specific items from the JD (company name, team, product, recent news, etc.). If the LLM produces a generic letter, mark as `cover_letter_specificity_low` and trigger escalation.

**Step 5c: Skill-gap notes**
- For each uncovered must-have, a one-sentence note: either "covered via [X] from your resume" or "gap: [Y]. Consider a 1-line cover-letter addition: '[suggested text]'."

**Step 5d: Model selection logic**
```
default = llm_default_provider + llm_default_model
if user_marked_important or cover_letter_specificity_low or in_ab_sample:
    escalate to llm_escalation.default_candidate
```

**Output:** `TailoredArtifact` row + rendered PDFs in object store. Token cost recorded.

**Cost:** ~$0.005/job at kimi-k2.6 (cheap tier), ~$0.04/job at deepseek-v4-pro (escalation). With ~10% escalation, average ~$0.009/job.

### 7.6 Stage 6 — ATS Validation (deterministic, free)

Sanity-check the generated artifacts before they reach the user:

- **Selectable text in PDF** (i.e., the PDF is not just an image). Check via `pdftotext`.
- **All must-have keywords present** in the resume (already enforced in 5a, but re-verify).
- **No tables, no images, no unusual fonts** (heuristic on the PDF + check the source HTML).
- **File size < 2 MB**.
- **No obviously fabricated content** (e.g., resume claims a job the user never had): heuristic check that the bullet list of the tailored resume is a subset of the bullets in the original resume (no invented accomplishments).

If validation fails, regenerate up to 2 times with stricter prompts. If still failing, mark the match as `tailoring_failed` and surface a manual-review notice.

### 7.7 Pipeline summary

```
Raw job (per source)
  → Stage 1: heuristic       ── kills ~50% of jobs, no LLM
  → Stage 2: parse           ── $0.0002/job
  → Stage 3: skill match     ── kills ~20%, no LLM
  → Stage 4: probability     ── kills ~10%, no LLM
  → Stage 5: tailor          ── $0.005-0.04/job (the only big cost)
  → Stage 6: validate        ── retry on failure
  → Top-25 per day per profile → User dashboard
```

**Independent testability:** each stage is a pure function or a small pipeline with explicit inputs/outputs. We can regression-test each stage with a frozen job corpus.

---

## 8. Apply Engine + Outcome Loop

### 8.1 Three apply modes

| Mode | Trigger | Action |
|---|---|---|
| **Auto-apply (API)** | User pre-approved, target ATS in `auto_apply_allowlist`, all gates passed | `POST` to the ATS apply endpoint with tailored resume + cover letter + application answers. Greenhouse, Lever, Ashby only. |
| **Assisted apply** | All gates passed, target is not auto-applyable | Bundle a "kit" (PDF resume, PDF cover letter, 3-5 application-question snippets, deep link to job) and present in the UI. User copies and submits in <2 minutes. |
| **Skip** | User marks "not interested" or "let me edit first" | Job moved to skipped list. Tailored artifact retained for 7 days then deleted. |

### 8.2 Conviction gating (runs before any submit)

```
✓ must_have_cov     >= profiles.tailoring_thresholds.must_have_coverage_min  (default 0.70)
✓ jd_quality        >= profiles.tailoring_thresholds.jd_quality_min          (default 0.40)
✓ comp in user range (or comp not listed AND user's comp preference is open)
✓ Resume passes Stage 6 ATS validation
✓ User has approved the tailored materials (in UI)
✓ Rate limit:        max applies/profile/day <= profiles.tailoring_thresholds.max_per_day
✓ (For auto-apply)   target source in profiles.auto_apply_allowlist
```

### 8.3 Application timing

- **Real-time queue:** when a high-score job arrives from a fast-update source (Greenhouse, Lever, Ashby), apply within 1 hour if auto-apply is enabled. Research consistently shows that applying within 24-48h of posting materially increases response rates.
- **Batch fallback:** end-of-day batch for jobs accumulated during off-hours.
- **Weekend avoidance:** default off (configurable per profile). Recruiters and hiring managers tend to read applications Tuesday-Thursday.
- **Staggering:** never fire 25 applications in the same second. Add jittered delay (1-15 minutes between submissions) to look human.

### 8.4 Outcome feedback loop

**Inputs:**
- **Manual:** user marks `interview / rejected / no_response / offer / withdrawn` in the UI.
- **Auto-detection:** for ATS-API applications, poll the ATS for status changes (Greenhouse has candidate status endpoints; Lever is more limited). Poll weekly.
- **Heuristic:** after 30 days with no status change, mark as `no_response`.

**Outputs (after ≥30 outcomes for a profile):**
- Recompute weights in `match_weight_overrides.weights` using logistic regression on the outcome data.
- For each source, compute: apply count, response rate, interview rate, offer rate. Surface "this source is converting at 1% — consider deprioritizing."
- For each level/role_function combination, compute fit-vs-outcome correlation. If the system is overestimating fit for some job types, lower the weights.

**Cold-start handling:** until 30 outcomes accumulate, use hand-tuned weights from §7.4.

### 8.5 Audit trail

Every application records:
- Snapshot of resume + cover letter at submit time (object-store keys, immutable)
- The exact prompt version (git-sha of `prompts/` directory at the time)
- Model and provider used
- Which must-haves were covered
- Target job URL, ATS source
- Submit timestamp
- All subsequent status changes

**The family can always answer "what did we actually send them?" without re-deriving.** This is the single most important compliance property.

---

## 9. Per-Profile Configurations (worked examples)

### 9.1 Banker — 28 yrs commercial banking

**Sources:** Greenhouse, Lever, Ashby, SmartRecruiters, Adzuna (US), The Muse, JSearch (low priority). USAJobs off. Remote boards off.

**LLM:** `opencode_zen` + `kimi-k2.6` default; escalate to `deepseek-v4-pro` for senior-level roles.

**Auto-apply:** enabled. Allowlist: `greenhouse, lever, ashby`.

**Tailoring thresholds:** `min_match_score=0.50`, `max_per_day=20`, `jd_quality_min=0.50`, `must_have_coverage_min=0.75`.

**Special handling:**
- Resume template: US 2-page.
- Tone: senior, results-oriented, banking-domain vocabulary.
- Cover letter style: direct, brief, references specific deal experience.

### 9.2 Client partner — 30+ yrs tech consulting

**Sources:** All Tier-1 + Tier-2 (heavy remote board usage). USAJobs off.

**LLM:** `opencode_zen` + `kimi-k2.6` default; escalate to `glm-5.1` for partner-level roles.

**Auto-apply:** enabled. Allowlist: `greenhouse, lever, ashby`.

**Tailoring thresholds:** `min_match_score=0.45`, `max_per_day=25`, `jd_quality_min=0.40`, `must_have_coverage_min=0.70`.

**Special handling:**
- Resume template: US 2-page, executive summary section.
- Tone: strategic, client-relationship, outcomes-focused.
- Cover letter: longer-form (4 paragraphs OK at this level), references industry/vertical.

### 9.3 MPH grad — 3 yrs

**Sources:** Greenhouse, Lever, Ashby, **USAJobs (primary)**, Adzuna (US, public-health keywords), The Muse, JSearch.

**LLM:** `opencode_zen` + `kimi-k2.6` default; cheap tier is fine for most public-sector roles. Escalate to `qwen3.7-max` for senior policy roles.

**Auto-apply:** **disabled**. USAJobs is manual-apply only. Other ATSes could auto-apply, but the user wants to review every public-sector application.

**Tailoring thresholds:** `min_match_score=0.40`, `max_per_day=15` (smaller pool), `jd_quality_min=0.40`, `must_have_coverage_min=0.70`.

**Special handling:**
- Resume template: US, 1-2 pages (recent grad, can be 1 page; 2 pages if more internships/research included).
- Tone: mission-driven, methodological, public-health specific vocabulary (epidemiology, biostatistics, program evaluation, health equity).
- Cover letter: explicit mission-alignment opener for NGO/nonprofit roles; specific KSAs (knowledge, skills, abilities) mapping for federal roles (USAJobs uses KSAs explicitly).

---

## 10. Cost Estimates

### 10.1 LLM costs (the main variable)

See §4 for the per-stage table. Headline: **~$20/month for the whole family** with the default-cheap-tier model and ~10% escalation to deepseek-v4-pro.

### 10.2 Other variable costs

| Item | Cost |
|---|---|
| JSearch (RapidAPI) | Free tier first, then $25/month if we exceed 250 calls/month |
| SerpApi (backstop only) | $50/month if activated |
| Adzuna | Free tier 250 calls/month; ~$50/month for higher volume |
| USAJobs | Free (with API key) |
| Domain name (if needed) | ~$12/year |
| Let's Encrypt TLS | Free |
| Hostinger VPS | User's existing cost |

**Conservative monthly run rate (LLM only):** $20-30.
**With paid aggregators (JSearch + Adzuna upgraded):** $70-100/month.

### 10.3 Infrastructure

- Hostinger VPS, 1-2 vCPU, 2-4 GB RAM. Postgres + MinIO + the app in Docker compose. Should fit comfortably in a small VM.
- ~5 GB of disk for Postgres, ~10 GB for object store (resume/cover letter PDFs), ~1 GB for application binaries.

---

## 11. Deployment

### 11.1 Docker Compose layout

```yaml
services:
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes: [./Caddyfile:/etc/caddy/Caddyfile, caddy_data:/data]
  app:
    build: .
    environment:
      DATABASE_URL: ...
      OPENCODE_ZEN_API_KEY: ...
      # (all secrets via env; never committed)
    depends_on: [postgres, minio]
  postgres:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    volumes: [miniodata:/data]
  # (optional) watchtower for image auto-update
```

### 11.2 Domain and TLS

- User provides a domain (or subdomain). Caddy handles Let's Encrypt automatically.
- We default to `app.<user-domain>`.

### 11.3 Backups

- Postgres: nightly `pg_dump` to a separate volume, retained 7 days. (Could be pushed to S3/B2 if desired.)
- Object store: versioned; old resume snapshots retained 90 days.

### 11.4 Monitoring

- Minimal: log to stdout, scrape via journalctl or Loki. We don't need a Prometheus/Grafana stack for a personal tool.
- Uptime check: simple cron from a different machine pings `/health` every 5 min and emails if down.

---

## 12. Privacy and Security

- **TLS everywhere** (Caddy + Let's Encrypt).
- **Argon2id** for any password hashes (no password storage for OAuth/magic-link users).
- **Secrets via env vars**, never committed. A `.env.example` documents required keys.
- **Object store is private** to the app container; PDFs not served directly. They go through the app with auth check.
- **LLM call logging:** we record the prompt + response for 30 days for debugging, then delete. (Could disable if user wants maximum privacy; trade-off is harder debugging.)
- **Resumes, cover letters, application history** are PII. Access is per-user; the admin can see all. We do not export to anywhere external.
- **Outbound LLM calls** send resume content to OpenCode Zen (or whichever provider is configured). If the user is uncomfortable with that, we can configure per-profile "no cloud LLM" — but per §1.4, all inference goes to external providers in this design.

---

## 13. Testing

Each stage in §7 is independently testable.

- **Unit tests:** per-stage pure-function tests (Stages 1, 3, 4, 6 are deterministic).
- **Golden corpus tests:** for Stages 2 and 5, maintain a frozen set of (resume, JD) → expected-tailored-output pairs. LLM output is non-deterministic, so we test structural properties (all must-haves present, comp range referenced, etc.), not exact strings.
- **Integration tests:** end-to-end with mock ATS endpoints (Greenhouse/Lever/Ashby all have public test instances).
- **Manual QA:** a small "tailor this one job and let me review" mode for the user to sanity-check before the cron runs.

---

## 14. Open Questions (deferred to implementation planning)

These are not blockers for the design but should be resolved before implementation:

1. **Auth method:** magic link via email vs username+password. Magic link is more secure (no password to leak) but requires email sending infrastructure. Username+password is simpler. Default: **magic link** via a transactional email provider (Resend or Postmark, free tier covers our volume).
2. **Notification channel:** how do we tell the family "new matches are ready"? Options: in-app only, email digest, push notification (requires service worker), Telegram bot. Default: **email digest** daily + in-app feed.
3. **Multi-language support:** currently US-primary. If a family member's profile needs Spanish, French, or Hindi JD parsing and tailoring, that's a Stage 2 / 5 prompt change. Default: **English only** for v1.
4. **Mobile UI:** design is responsive (Tailwind), but some flows (uploading a resume, reviewing tailoring) work better on desktop. Acceptable for v1.
5. **LinkedIn data refresh:** how often to re-import LinkedIn profile data. Default: **on-demand** (user clicks "refresh from LinkedIn").
6. **Backup and disaster recovery:** see §11.3. Acceptable for v1.

---

## 15. Glossary

- **ATS** — Applicant Tracking System. The software companies use to receive and process applications (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, etc.).
- **JD** — Job Description.
- **KSA** — Knowledge, Skills, Abilities. The format USAJobs uses for federal job applications.
- **MPH** — Master of Public Health.
- **Tailoring** — customizing a resume and cover letter for a specific job, mirroring the JD's keywords and emphasizing relevant experience.
- **Must-have coverage** — the fraction of "required" items in a JD that the candidate's resume credibly addresses.
- **Probability of interview** — composite score estimating the likelihood the application leads to an interview call.
- **Conviction gate** — pre-submit checks that ensure we only apply to jobs we've verified are worth applying to.

---

## 16. Out of Scope (v1)

- Cover letter generation for non-English roles
- Auto-apply via browser automation
- LinkedIn Easy Apply integration
- Resume scoring against arbitrary JDs the user manually pastes (could be a v2 feature)
- Mobile native apps
- Multi-tenant SaaS mode

---

**End of design spec.**
