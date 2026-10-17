# Antigravity Usage Analytics Dashboard

A local, read-only dashboard over the token usage recorded by the Antigravity CLI.
It reuses the existing extractor (`agy_usage.py`) instead of reimplementing it, and
computes every cost itself from a **dated, versioned price catalog**.

Nothing is uploaded. The app binds to `127.0.0.1` only and Streamlit telemetry is off.

---

## 1. Quick start (Windows PowerShell)

```powershell
cd $env:USERPROFILE\PycharmProjects\AntigravityUsageDashboard

# One-time setup (only if .venv is missing)
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run (activates nothing global; uses the project venv)
.\run.ps1
```

`run.ps1` picks a free port starting at 8501, starts Streamlit on localhost, and opens
your browser. Double-click `run.bat` for the same thing without a terminal.

Tests:

```powershell
.venv\Scripts\python.exe -m pytest
```

> On this machine the Python launcher is `py` — plain `python` is broken on PATH.
> The dashboard just imports the extractor, so it does not care; the Data & Jobs page
> uses whatever `python_executable` the config says.

---

## 2. What it reads

| | |
|---|---|
| Usage source | `~/.gemini/antigravity-cli/brain/<conversationId>/.system_generated/logs/transcript.jsonl` (read-only, never written) |
| Extractor | `~/docs/superpowers/scripts/agy_usage.py` — imported and called, never modified |
| Prices | `config/pricing.json` (falls back to the built-in catalog) |
| Config | `config/config.json` (falls back to `config/config.example.json` defaults) |
| Snapshots | `data/snapshots.db` (SQLite, optional) |
| Job logs | `data/logs/` (stdout/stderr per run, `last_run.json`, lock file) |
| Deep scan also reads | `transcript_full.jsonl` (richer than `transcript.jsonl`), `history.jsonl` (workspace), `settings.json` (current model), `messages/*.json` + `read.json`, `subagents/*.json`, `steps/*/output.txt` sizes, `*.md.metadata.json` artifacts — all read-only |

Token fields exist **only from 2026-10-05 onward**; older sessions are empty shells and
are skipped. A full scan takes ~1.5 s and is cached for 30 s.

---

## 3. Data flow

```
ACLI logs ──► agy_usage.scan(root) ──► sessions{} / daily{} dicts
                                          │
                     source.scan_usage()  │  normalize to pandas
                                          ▼
                     sessions_df / daily_df (tokens only, no cost)
                                          │
        pricing.Catalog.price_on(model, date) ──► PriceEntry (USD per 1M tokens)
                                          ▼
                     metrics.*  ──►  totals, costs, blended rate, tokens/₹, comparisons
                                          │
                  ┌───────────────────────┼──────────────────────────┐
                  ▼                       ▼                          ▼
            Streamlit pages         stats.py forecasts        snapshots.ingest()
            (6 pages)               (linear/bootstrap/MC)      (idempotent SQLite)
```

A second, heavier pass feeds the Deep Signals page. It is read-only and separate
from the token scan, because it answers different questions:

```
ACLI logs + history.jsonl + settings.json + messages/ + subagents/ + artifacts
                              │
                    deep.scan_deep(root)          ~7 s, cached 15 min
                              ▼
   tool_calls · turnarounds · gap time budget · failures · denials · commands
   model switches · session/workspace meta · artifacts · messages · counters
                              ▼
                    Deep Signals page (4 tabs)
```

Cost is **never read from the logs** — it does not exist there. It is always
`tokens × price` for the model and period you select.

---

## 4. The six pages

**Overview** — KPI cards (total/fresh/cached/output tokens, calls, sessions, API-equivalent
cost, actual subscription spend, tokens per ₹ spent, blended API rate, cache-hit rate),
daily token + cost trend, fresh-vs-cached split, best/worst days, last refresh time.

**Usage Explorer** — interactive time series (fresh / cached / output / total / calls /
sessions) with zoom, hover and legend toggling; calls and sessions per day; top sessions;
session-type split; searchable daily and session records with CSV export.

**Model Cost Lab** — the same observed workload priced against Gemini Flash/Argon/Pro,
Claude Haiku/Sonnet/Opus, OpenAI tiers and hosted open-weight models. What-if sliders move
the cached-token ratio, prompt volume and output volume. Shows cost, cost per 1M tokens,
tokens per ₹, and a multiple-of-cheapest column. Subscription spend is displayed separately
from API-equivalent spend, never netted against it.

**Forecast** — linear extrapolation (baseline), bootstrap resampling, Monte Carlo simulation,
and Holt's trend model (enabled only with ≥14 days). Configurable growth/drift/volatility,
10th–90th percentile bands, cumulative low/median/high, per-day download, daily/weekly/monthly
aggregation of *measured* data. Modelled values are visually and textually separate from logged ones.

**Deep Signals** — second-order analytics from a separate deep scan (~7 s, cached 15 min):
unit economics (cost per call / session / agent-busy hour, autonomy ratio, a labelled waste
proxy), spend per workspace, cache-miss calls per day, busy-vs-idle hours, tool turnaround
medians, tool-mix and MCP-server leaderboards, slowest commands with exit codes, async/scheduled
work, failure feed with the most repeated strings, approval denials, context-pressure counters,
model-switch timeline, subagent share, artifacts, inter-agent messages and interaction counters.

**Data & Jobs** — runs the extractor's CLI as a background process: report selection, live
status, start/end/duration/exit code, full stdout and stderr, configurable log location,
lock file against concurrent runs, automatic refresh on success, plus optional SQLite snapshot
history with idempotent ingestion.

---

## 5. Configuration

`config/config.json` (copy of `config.example.json`):

```json
{
  "brain_root": "~/.gemini/antigravity-cli/brain",
  "extractor_script": "~/docs/superpowers/scripts/agy_usage.py",
  "python_executable": "py",
  "db_path": "data/snapshots.db",
  "log_dir": "data/logs",
  "extraction_timeout_seconds": 180,
  "subscription": { "amount": 0.0, "currency": "INR", "period_days": 30, "label": "Antigravity plan" },
  "fx": { "USD_INR": 88.0 },
  "reporting_currency": "INR"
}
```

`subscription.amount` is **what you actually pay**. It is used only for
"tokens per rupee actually spent"; leave it at 0 and that metric reads 0 instead of infinity.
The sidebar lets you change the amount, the FX rate, the pricing model and the theme for
the current session without touching the file.

### Prices

`config/pricing.json` has one entry per model per date range (`effective_from` /
`effective_until`, USD per 1M tokens for input / cached input / output). To be exact for a
new period, add a version; the dashboard picks the version covering the observed date and
flags anything else as an **estimate** rather than silently using today's rate.
`config/pricing.example.json` is the generated copy of the built-in catalog.

---

## 6. Calculations (all in `agy_dash/metrics.py`, all tested)

* `total = fresh input + cached input + output` — the three categories are mutually
  exclusive in the source (fresh excludes cache reads).
* Equivalent API cost `= Σ (tokens × price) / 1e6`, per model and period.
* Blended API rate `= total modeled cost / total tokens × 1e6`.
* Tokens per ₹ spent `= observed tokens / actual subscription spend`.
* Cache-hit rate `= cached / (fresh + cached)`.
* Every division goes through `safe_div`: zero denominators return a documented default,
  and NaN never propagates.
* `verify_consistency()` re-checks reported totals against the source rows and *surfaces*
  mismatches on the Data & Jobs page instead of correcting them.

---

## 7. Limitations you should know

1. **Model attribution is not in the logs.** Transcripts record no per-call model, so all
   usage is priced with the single model you select. Re-pricing could shift totals.
2. **Equivalent cost is not cash.** Inside a subscription quota the marginal spend is zero;
   the API figure is what this usage *would* bill at list prices. The gap between subscription
   and API-equivalent cost is neither money saved nor money paid.
3. **Ten observed days is not six months.** Forecast methods describe the recent routine;
   they cannot establish long-run behaviour. Extrapolating past ~2× the observed window is
   unreliable, and the pages say so.
4. **Bootstrap can only replay what it has seen** — it can never forecast a new record day.
5. **Historical prices.** Where no price version covers a period, the nearest earlier version
   is used and labelled an estimate.
6. **Open-weight/other-vendor prices in the built-in catalog are approximate list prices**
   (`verified: false`), meant for comparison, not invoicing.
7. **Live drift.** Logs keep growing while agent sessions run; the Overview shows the scan time.
8. Not included: context-cache storage fees, image generation, print-mode differences.
9. **The time budget is an approximation.** Busy and idle hours come from gaps between
   consecutive step timestamps, capped at 4 h, so an overnight pause counts as 4 h rather than
   9. Granted approvals leave no trace, so their waiting time hides inside the planner→result gap.
10. **Command durations are windows, not stopwatches.** They are the CLI's own
    `Created At`→`Completed At` stamps, which for async commands include waiting. A result block
    is only accepted when it proves it is a command result (exit code or cancellation note),
    otherwise the pairing would invent hours-long "commands".
11. **Tool turnaround includes generation and dispatch**, not just tool execution, and parallel
    tool calls in one step share one gap. The tool list comes from `tool_calls[].name`.
12. **Workspace attribution comes from `history.jsonl`.** Subagent sessions inherit their
    parent's workspace; sessions with no history entry are reported as unattributed rather than
    guessed. The logs contain no per-call model, so the model-switch panel is a timeline, not
    per-call attribution.
13. **Waste estimate is an order of magnitude**, not accounting: failures × average observed
    cost per call. It is capped at 100 % of observed spend and labelled as a proxy in the UI.

---

## 8. Tests

`pytest` (114 tests):

| File | Covers |
|---|---|
| `tests/test_metrics.py` | token totals, cost per category, hand-verified Oct 5 row, blended rate, currency, subscription metrics, safe division, what-if scaling, model comparison, consistency checks |
| `tests/test_pricing.py` | dated versioning, 2027 price change, historical-estimate flagging, catalog file override, broken-file fallback |
| `tests/test_stats.py` | linear slope/flat/growth, bootstrap determinism and bounds, Monte Carlo drift/non-negativity, Holt gating, aggregation totals |
| `tests/test_jobs.py` | success, failure, timeout kill, concurrent-run refusal, lock release and stale locks, missing script, argv-not-shell, last-run record |
| `tests/test_snapshots.py` | idempotent ingestion, upsert on change, run log, last-success |
| `tests/test_source.py` | extractor reuse, normalization, missing paths, date filters, empty results |
| `tests/test_deep.py` | tool-name truth + corrupted-name filtering, MCP server parsing, gap capping, busy/idle split, command duration/exit-code guards, failure text, denials, model-switch cleaning, workspace inheritance, per-day counters, unit economics, waste bounds |
| `tests/test_app_smoke.py` | real extractor against a synthetic brain dir, CLI run through the job runner, and every dashboard page rendered via Streamlit's `AppTest` |

Fixtures use the numbers from the supplied usage summary and the hand-verified rows in it —
as test data, never as the live dataset.

---

## 9. File map

```
app.py                        Streamlit entry point: sidebar, global filters, routing
agy_dash/
  config.py                   defaults, config.json merge, logging
  source.py                   import the existing extractor, normalize to DataFrames
  metrics.py                  all core calculations (pure)
  pricing.py                  dated/versioned price catalog + lookups
  stats.py                    linear / bootstrap / Monte Carlo / Holt + aggregation
  jobs.py                     subprocess job runner, timeout, lock, last-run record
  snapshots.py                SQLite schema + idempotent ingestion
  deep.py                     second read-only pass: tools, time, failures, workspaces
  ui/
    common.py                 theme, CSS, formatters, chart config, shared Ctx
    overview.py               page 1
    explorer.py               page 2
    lab.py                    page 3
    forecast.py               page 4
    deep_signals.py           page 5
    data_jobs.py              page 6
config/
  config.example.json         configuration example (copied to config.json)
  pricing.example.json        generated copy of the built-in price catalog
tests/                        8 test modules + fixtures
run.ps1 / run.bat             Windows launchers
requirements.txt              streamlit, plotly, pandas, numpy, pytest
.streamlit/config.toml        localhost-only, no telemetry, dark theme defaults
```

**Created:** everything under `PycharmProjects/AntigravityUsageDashboard/`.
**Modified: nothing.** `agy_usage.py`, the Antigravity brain directory and the existing
`.gemini` state were only read.
