# pa-health — Package instructions

Wraps `garminconnect` and normalises daily data through `get_health(date_str)`. Read private user instructions for personal wellness preferences; never add actual measurements, thresholds, account behavior or personal history here.

## Data quality

- Check `ok` before reporting. Authentication failure or no loaded data returns `ok: False`; missing values are not zero.
- Data may sync incrementally. Check timestamps and completeness and re-fetch when partial data is suspected. A disagreement with self-report does not prove a sync fault; describe unresolved differences accurately.
- `hrv` comes from `hrvSummary.weeklyAvg` and may be unavailable. `avg_stress` is a separate vendor stress score, not an HRV measurement or substitute in milliseconds. Do not relabel it as HRV.
- Calendar entries show scheduled plans, not proof of what happened. Record user-provided context separately from device readings and inference.
- Device alerts are not diagnoses. Avoid unsupported medical conclusions or reassurance from a threshold alone.

## Activities and alerts

`activities` contains normalised `id`, `name`, `type`, `start`, `distance_km`, `duration_min`, `avg_hr`, `max_hr`, `calories`, `vo2max`, `intensity_minutes`, `is_pr`, `training_load`, `aerobic_te`, `anaerobic_te`, `elevation_gain_m` and `avg_pace_min_km` (None without distance). Include relevant recorded activities in health summaries. Missing distance is `None`, not zero. An empty session list is `[]`. Activities can make a day `ok` even if the wellness summary is incomplete.

`abnormal_hr` contains device alerts with `date`, `time`, `bpm`, `threshold` and `ts`. Follow private preferences about asking for context. Use `uv run pa-health alerts` (which wraps `unlabelled_hr_alerts()`) to avoid repeated questions and store responses only in private wellness logs.

For date ranges, use `uv run pa-health activities --from DATE --to DATE` (or `get_activities_range()`). Compare data across appropriate periods and state missing coverage.

## Training log

`pa-health workout` wraps `pa_core.training`: one record per session (planned, done, missed or skipped) in `activity/training/sessions.jsonl`, with sets, reps and weights, RPE and Garmin metrics. The `personal-trainer` skill says how to use it.

- `sync` imports Garmin activities. It merges into a same-day session of the same type (or an untyped plan) and skips activities already imported, so it is safe to re-run. It never writes habit events.
- `log` closes the day's matching plan rather than adding a duplicate, and ticks today's Exercise habit once.
- Exercise specs: `name=3x10@50`, `name=3x10@10/side`, `name=12@40,10@45`, `name=3x5` (bodyweight).

## Authentication and privacy

Tokens live in `_token_dir()` and refresh through `_authenticated_client()`. Keep tokens, exports, health logs and account-specific troubleshooting in ignored local storage. Use synthetic fixtures only.

## Usage

```bash
uv run pa-health day [--date YYYY-MM-DD] [--json]                 # one day, normalised by get_health()
uv run pa-health activities [--days 7 | --from DATE --to DATE] [--json]
uv run pa-health alerts [--days 2] [--json]                     # HR alerts with no hr_context entry yet
uv run pa-health workout plan|log|update|sync|history|week      # training log; see the personal-trainer skill
```

Command output contains private data: do not paste it into tracked documentation or public issues.
