# Public Social Signal Pipeline

## Objective

Collect up to 100 useful public signals per day about high-attention AI companies, influential builders, model releases, Agent ecosystems, industry changes, business models, funding, and IPO activity. The collector does not pad the daily note when fewer than 100 items pass the quality threshold.

## Access Boundary

The pipeline uses only:

- GitHub public REST endpoints for watched users and repository releases
- Public RSS or Atom feeds added to the configuration
- Specific public post URLs supplied by the user
- Optional authorized credentials such as `GITHUB_TOKEN`

It does not bypass login walls, CAPTCHAs, robots controls, rate limits, or anti-automation systems. X and Facebook account names in the watchlist are discovery targets only. Automatic discovery for those platforms requires an authorized API, a compliant data provider, or user-supplied public post URLs.

## Storage

```text
local/cache/http/                              # ETag response cache
local/cache/social/YYYY-MM-DD.json             # machine-readable features
../commercial-insight-vault/10_Sources/Social/
  YYYY-MM-DD-social-signals.md                 # human-readable daily evidence
```

Each signal records platform, source type, author, company, URL, timestamp, categories, excerpt, relevance, heat, credibility, recency, novelty, same-day company activity, business value, evidence status, content angles, and verification requirements. IDs seen on a previous day are skipped for 45 days.

## Run Once

```bash
python3 scripts/social_collector.py
python3 scripts/knowledge_store.py index
```

The unauthenticated GitHub limit is sufficient for the initial watchlist. An optional token increases the allowance:

```bash
export GITHUB_TOKEN="your-fine-grained-token"
python3 scripts/social_collector.py
```

Do not commit the token or place it in the watchlist.

## Add Public X Or Facebook Posts

Edit `config/social_watchlist.json` and add specific URLs to `public_post_urls`. The page must be readable without login and expose public metadata. If the platform returns only a login page, the collector records an error and stops processing that URL.

## Daily Schedule On macOS

Default: 08:30 local time.

```bash
sh scripts/install_daily_social_job.sh
```

To select another time during installation:

```bash
SOCIAL_JOB_HOUR=9 SOCIAL_JOB_MINUTE=15 sh scripts/install_daily_social_job.sh
```

Logs are written under the ignored `local/logs` directory. The job writes to the private Vault and rebuilds the local knowledge index after collection.
