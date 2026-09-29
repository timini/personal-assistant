# 1. PA runtime architecture: scheduled layers on a self-hosted host

Date: 2026-08-23

## Status

Proposed. Amended 2026-08-23 after building and researching parts of it — see
**Amendments** at the end, which supersede four of the decisions below. Note that
Amendment 4 supersedes Amendment 2, written the same day.

## Context

The PA is a uv workspace of nine Python packages driven interactively by Claude Code. It
works, but four problems have accumulated, and they are frequently treated as one problem
with one fix. They are not.

1. **Cost and token burn.**
2. **State is forgotten between sessions.**
3. **Nothing happens unless a session is opened manually.**
4. **There is a lot of hand-written code to maintain.**

Measured on 2026-08-23:

| | |
|---|---|
| Owned code | 5,465 lines of Python, 9 packages, 25 test files |
| Largest packages | `pa-core` 1,495 · `pa-notion` 1,117 · `pa-google` 882 · `pa-browser` 828 |
| Scheduled jobs | None. No crontab, no scheduling LaunchAgent |
| Health tracking | Not implemented |
| Context assembly | `pa_core/context.py`, with a consistent `_fetch_*` function per source |
| State stores | Three, uncoordinated: agent memory files, `activity/daily/*.json`, Notion task notes |

Health tracking is now a firm requirement rather than the "future extension" described in
`AGENTS.md`. The wellness and coaching logic already branches on energy and mood; without
objective sleep and recovery data it is guessing.

A dedicated always-on host (Mac mini, reachable over Tailscale) became available on
2026-08-22, which changes what is practical.

### Diagnosis

Each problem has a distinct cause, which is why a single rewrite would address at most one
of them.

**Problem 3 is not an architectural failure.** No scheduler was ever built. It is the
cheapest of the four to fix and requires no redesign.

**Problem 1 is caused by doing deterministic work inside an agent loop.** Fetching a
calendar, listing tasks, sending a message and running a backup are not reasoning tasks,
and the Python to do them already exists. Today they execute inside an interactive session,
so each one is mediated by a model turn, and every session re-reads a large instruction
prefix. The model is genuinely needed only for judgement: triage decisions, prioritisation,
coaching tone, and deciding what to surface.

**Problem 2 is caused by state being scattered across three stores** that do not reference
each other, so every session re-derives the current position by re-querying all of them.

**Problem 4 is partly self-inflicted duplication.** First-party MCP connectors for Notion,
Gmail, Google Calendar and Google Drive are now available and cover a substantial share of
what `pa-notion` and `pa-google` implement by hand.

## Decision

Keep Claude Code as the runtime. Do not rewrite. Split the work by what actually requires a
language model, and run it on the self-hosted always-on host.

### Three layers

**Layer 1: deterministic collector, no model, scheduled.** A `pa-core collect` command,
triggered by a LaunchAgent, writes one dated state file to `activity/state/YYYY-MM-DD.json`
containing calendar, tasks, inbox summary, habits, weather, health and task-flow stats. It
reuses the existing `_fetch_*` functions in `pa_core/context.py` rather than introducing a
parallel implementation. This is the single largest cost lever: routine fetching stops being
a model turn.

**Layer 2: scheduled agent runs, model, cheap.** LaunchAgents invoke headless `claude -p`
for the morning briefing, evening review and Sunday weekly review. Each run reads the
pre-collected state file instead of re-querying sources, so the prompt stays small and
stable. Three cost controls, in order of expected impact: prompt caching on the stable
instruction prefix; per-job model selection, reserving the most capable model for
interactive work; and reduced effort on routine runs.

**Layer 3: interactive sessions, unchanged.** Conversation and ad-hoc work. This part
already works and is deliberately not modified.

### State of play

Introduce a single `activity/state-of-play.md`, rewritten by the evening run, recording
live projects, what moved, what is blocked and on whom, and what is decided as opposed to
merely proposed. Sessions read that one file rather than re-deriving from three stores. The
existing memory files remain for durable facts; the daily JSON remains as the event log.

### Health tracking

Health enters through a source adapter behind a single `_fetch_health()` in
`pa_core/context.py`, following the existing `_fetch_*` convention, backed by a new
`pa-health` package. Downstream consumers depend on a stable shape, never on a vendor.

The shape carries sleep duration and quality, resting heart rate, HRV, a recovery measure,
activity, and a timestamp. It surfaces in the existing "How You're Doing" section of
`briefing.py`.

A failed or stale source degrades to missing data. It must never fail a briefing.

## Consequences

### Positive

- Problem 3 is fixed by the first increment, before any redesign.
- Problem 1 is addressed structurally, by moving deterministic work out of the model loop,
  rather than by prompt trimming.
- Problem 2 gains a single authoritative read.
- Problem 4 has a concrete path: an estimated 1,000 to 2,000 lines removable from
  `pa-notion` and `pa-google`.
- All existing integrations, instruction files and accumulated behaviour are preserved.
- Health data can be added without any consumer depending on the vendor.

### Negative

- The host becomes a single point of failure. It runs FileVault with automatic login
  disabled, so a power cut leaves the PA down until someone is physically present. This is
  acceptable for an assistant, but it must be a known limitation before anything
  load-bearing depends on it.
- Scheduled runs consume budget whether or not anyone reads the output.
- Layer 1 and Layer 2 must be kept in step. A field added to the collector without a
  corresponding consumer change is silently ignored.
- Consolidating onto MCP connectors risks regressing behaviour that looks incidental but is
  not, notably thread-level Gmail archiving.

### Explicitly retained

Some hand-written code is not duplicated by any connector and stays:

- `outlook.py` and `outlook_sync.py`, AppleScript against Legacy Outlook.
- `pa-browser`, the only route to a real logged-in browser profile.
- The Notion Lane field and the task-flow snapshot logic.
- Thread-level Gmail archiving, which is easy to regress and already documented.

## Alternatives considered

**Claude Agent SDK, self-hosted.** Claude Code packaged as a library, giving a long-running
daemon with programmatic control of the loop. Rejected for now: it increases owned code,
directly against problem 4, and headless `claude -p` delivers most of the benefit. This
remains the upgrade path if the scheduled-CLI approach proves limiting.

**Managed Agents with scheduled deployments.** Anthropic hosts both the loop and the cron,
with persisted versioned configs and managed memory. Genuinely strong against problems 2, 3
and 4. Rejected because the decision is to self-host, and because `pa-browser` and the local
credential and keychain setup cannot move into a hosted sandbox.

**A workflow orchestrator such as n8n or Home Assistant.** Capable at plumbing, incapable at
judgement. The PA's value is concentrated in triage and coaching decisions, which is exactly
what these tools cannot provide. It would add a system to maintain rather than remove one.

**Rewrite from scratch.** Rejected. The diagnosis does not support it. Three of the four
problems are addressable incrementally, and a rewrite would discard a large body of
accumulated, working, integration-specific behaviour.

## Health source options

Recorded because the reliability characteristics differ sharply and drove the adapter
decision.

| Source | Assessment |
|---|---|
| Google Health Connect (Android) | First-party and stable. Garmin syncs into it. Requires Android |
| Apple Health via an export app posting to a REST endpoint | Robust and well established. iPhone only. Health data is inaccessible while the device is locked, so exports run only when unlocked |
| `python-garminconnect` | Richest Garmin-native data. Unofficial, backed by scraped session auth. Broke in March 2026 when Garmin changed authentication. Acceptable as enrichment, unacceptable as the only path |
| Garmin GDPR bulk export | Complete and reliable, but manual and non-incremental. Backfill only |

The first-party platform matching the phone is the primary source. `python-garminconnect`
may be layered on later for Garmin-specific metrics, on the explicit understanding that it
will break again.

## Implementation sequence

Red-green TDD throughout, per the standing rule in `AGENTS.md`.

1. Schedule the existing `pa-core checkin --telegram` via a LaunchAgent. Smallest possible
   change, fixes problem 3 immediately, and proves the pattern.
2. Add `pa-health` and `_fetch_health()`, with recorded fixtures so tests never hit the
   network.
3. Add `pa-core collect` and repoint scheduled runs at the state file.
4. Apply prompt caching and per-job model selection.
5. Add the state-of-play document, written by the evening run.
6. Consolidate onto MCP connectors, only where verified to work in headless runs.

Record a token baseline for one morning briefing **before** starting step 3. Without it,
there is no way to answer whether any of this made things cheaper.

## Open questions

1. ~~Which mobile platform, since it selects the primary health source.~~ **Answered: Android
   (Pixel 9).** See Amendment 2.
2. Whether "cost" means spend or subscription usage limits. If the latter, per-job model
   selection matters more than prompt caching. Still open.
3. Whether the MCP connectors function in headless `claude -p` runs. Now moot — see
   Amendment 3.

---

# Amendments, 2026-08-23

Written the same day, after building the first pieces. Kept as amendments rather than edits
so the reasoning that turned out to be wrong stays visible.

## Amendment 1 — the Layer 1 collector is rejected

**The decision above proposed caching collected context to a dated state file. That was
built, measured, and then reverted. Do not rebuild it.**

It worked, and the numbers were good: a cold fetch of all sources is 18.5s of network I/O,
a cache hit is 0.04s. The problem is not performance, it is correctness.

The context bundle mixes data with completely different volatility:

| Cached | Tolerates an hour? |
|---|---|
| Weather, habits, stats, completed counts | Yes — the last two are local files anyway |
| Calendar | Usually, though not guaranteed |
| **Inbox** | **No.** New mail arrives constantly |
| **Tasks** | **No, and worst of all.** Tasks are mutated continuously during a session |

The task row is fatal. On the day this was written, dozens of tasks were closed, discarded
and re-parented over a few hours. A session served a cached task list would act on tasks
that no longer existed, and would do so silently.

Two failure modes were found while building it. First, caching the Telegram and WhatsApp
queues meant a later cache hit would surface messages already acknowledged and miss
anything since — patched by never caching those. Then the same argument was pointed out to
apply to tasks and inbox, which is most of the value. What remained cacheable was weather
and some local-file reads.

**The saving was 18 seconds. The cost was a class of silent staleness bugs in the data the
assistant acts on most.** Not worth it. Layer 1 as originally specified is withdrawn;
Layers 2 and 3 stand.

One thing from that work is worth keeping in mind: three existing tests were found to be
patching a path they thought was live, silently hitting the network, and one was attempting
a real Telegram send during `pytest`. That was pre-existing and only surfaced because the
call path moved.

## Amendment 2 — health source is Google Health Connect

> **SUPERSEDED the same day by Amendment 4. Both of the claims below are wrong.** Kept
> because the way it was wrong is instructive: the decision was made from a search result
> rather than from the vendor's actual capability matrix.

The mobile platform is **Android, a Pixel 9**, which settles the open question. Primary
source is **Google Health Connect**: first-party, stable, and Garmin Connect syncs into it.
This avoids the unofficial Garmin libraries entirely, which is the right outcome given they
broke in March 2026.

The adapter design is unchanged — one `_fetch_health()`, consumers depend on a shape rather
than a vendor.

**One gap to research before designing further.** Health Connect has no direct equivalent of
the iOS export apps that POST to a REST endpoint. Getting data off the device needs either a
Health Connect reader app or an automation tool such as Tasker. That route should be
established before any code is written.

## Amendment 4 — health source inverted: Garmin direct, Health Connect as backstop

Amendment 2 was researched properly a few hours after it was written, and both of its load-
bearing claims turned out to be false.

**Claim 1, that the unofficial Garmin libraries are broken: wrong.** They broke in March
2026 when Garmin tightened Cloudflare TLS fingerprinting, which killed `garth`, the shared
auth layer under most of the Python ecosystem. `python-garminconnect` did not die with it:
it dropped `garth`, rebuilt login on `curl_cffi` TLS impersonation with multi-strategy
fallback and MFA support, and shipped twelve releases between April and August. Verified
independently: **0.3.11, released 19 August 2026**, `curl_cffi` in the dependencies with no
`garth`, zero open issues, HRV documented.

The original claim traces to a search result asserting that new logins "do not work at all",
published by a site selling a paid alternative. A vendor-interested source was taken at face
value and written into a decision record.

**Claim 2, that Health Connect can carry the data: wrong, and this is the decisive one.**
Garmin deliberately withholds its proprietary metrics from Health Connect. **Body Battery
and HRV Status do not sync**, nor do training load, training status, stress, or intensity
minutes. What does cross is sleep, resting and workout heart rate, steps, calories,
workouts, weight and SpO2.

The shape this ADR specifies requires HRV and a recovery measure. **Health Connect is
structurally incapable of supplying them.** No amount of export plumbing fixes that, because
the data never reaches the device.

### Revised decision

**Primary: `python-garminconnect`, running server-side on the mini.** The only route that
delivers the full shape. No phone in the loop, no Android battery optimisation to fight, and
the output is already Python. Roughly an hour to set up: install, one interactive login to
mint tokens, then a scheduled daily pull.

Engineer for the break rather than hoping it will not come: cache tokens
(`~/.garminconnect/garmin_tokens.json`), fail loudly and visibly on auth errors rather than
silently returning nothing, and rate-limit — 429s appear in the issue tracker. Reliability is
best described as *medium and actively defended*. A break means "pin and wait for an upstream
patch", not "route dead".

**Backstop: Health Connect scheduled export to Google Drive.** Google's own feature, no
third-party code on the phone, roughly ten minutes to enable. Produces a ZIP containing an
unencrypted SQLite database, and this project already has Drive access. It cannot carry HRV
or Body Battery, but when Garmin next changes auth, sleep and resting heart rate keep
arriving daily while the primary route is repaired.

**Not adopted: the webhook app route.** A genuine Android equivalent of the iOS export apps
does exist and is actively developed, contrary to Amendment 2. It is skipped because it is a
third path to the subset of data the other two already cover, and it inherits the same Garmin
data ceiling.

**Not available: Garmin's official Health API.** Partner approval requires a legal entity;
personal applications are refused.

### One thing to check before building

That Garmin withholds Body Battery and HRV from Health Connect is load-bearing for this whole
decision, and it comes from three third-party sources that agree with each other rather than
from Garmin's own documentation, which would not render. **Open the Garmin Connect app's
Health Connect permission screen and confirm the data-type list before writing any code.**
Five minutes, and it validates the premise the design rests on.

## Amendment 3 — MCP consolidation is withdrawn

The decision above proposed replacing hand-rolled clients with first-party MCP connectors,
targeting 1,000 to 2,000 lines removed from `pa-notion` and `pa-google`.

**Two days of sustained use argue against it.** The line count is real, but so is the
behaviour those lines encode, and it is used constantly rather than occasionally: the Notion
Lane field, the parent-item relations, the task-flow snapshot, promote-to-Google-Tasks and
its sync, and on the Google side the thread-level Gmail archive and the Outlook AppleScript
bridge. All of these came up repeatedly in ordinary daily work, and none is something a
generic connector provides.

The original assessment treated this code as duplicated. It is better described as a thin
layer of genuinely custom behaviour over an API that happens to also be reachable another
way. Removing it would trade a maintenance cost that is currently low for a regression risk
that is not.

**Withdrawn as a planned step.** Revisit only if a specific module becomes a real burden,
and then module by module rather than wholesale.

## Status of the implementation sequence

| Step | State |
|---|---|
| 1. Scheduling | **Partly done.** A weekly task-flow report is emailed by a LaunchAgent. The daily checkin is not yet scheduled. |
| 2. Health adapter | Unblocked. Source settled by **Amendment 4** (Garmin direct, Health Connect backstop), which supersedes Amendment 2 |
| 3. Collector | **Withdrawn** — Amendment 1 |
| 4. Prompt caching + model choice | Not started. Record a token baseline first. |
| 5. State-of-play document | Not started. **Now the most valuable remaining piece**, and unaffected by Amendment 1: it addresses what the assistant *knows*, not what it *fetches*. |
| 6. MCP consolidation | **Withdrawn** — Amendment 3 |
