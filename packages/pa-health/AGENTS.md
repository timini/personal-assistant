# pa-health — Package instructions

Wraps `garminconnect` and normalises daily data through `get_health(date_str)`. Read private user instructions for personal wellness preferences; never add actual measurements, thresholds, account behavior or personal history here.

## Data quality

- Check `ok` before reporting. Authentication failure or no loaded data returns `ok: False`; missing values are not zero.
- Data may sync incrementally. Check timestamps and completeness and re-fetch when partial data is suspected. A disagreement with self-report does not prove a sync fault; describe unresolved differences accurately.
- `hrv` comes from `hrvSummary.weeklyAvg` and may be unavailable. `avg_stress` is a separate vendor stress score, not an HRV measurement or substitute in milliseconds. Do not relabel it as HRV.
- Calendar entries show scheduled plans, not proof of what happened. Record user-provided context separately from device readings and inference.
- Device alerts are not diagnoses. Avoid unsupported medical conclusions or reassurance from a threshold alone.

## Activities and alerts

`activities` contains normalised `id`, `name`, `type`, `start`, `distance_km`, `duration_min`, `avg_hr`, `max_hr`, `calories`, `vo2max`, `intensity_minutes` and `is_pr`. Include relevant recorded activities in health summaries. Missing distance is `None`, not zero. An empty session list is `[]`. Activities can make a day `ok` even if the wellness summary is incomplete.

`abnormal_hr` contains device alerts with `date`, `time`, `bpm`, `threshold` and `ts`. Follow private preferences about asking for context. Use `unlabelled_hr_alerts()` to avoid repeated questions and store responses only in private wellness logs.

For date ranges, use `client.get_activities_by_date(start, end)` and `normalise_activity`. Compare data across appropriate periods and state missing coverage.

## Authentication and privacy

Tokens live in `_token_dir()` and refresh through `_authenticated_client()`. Keep tokens, exports, health logs and account-specific troubleshooting in ignored local storage. Use synthetic fixtures only.

## Usage

```python
from pa_health.client import get_health

health = get_health()
if health["ok"]:
    for activity in health["activities"]:
        print(activity["type"], activity["distance_km"])
```

Command output contains private data: do not paste it into tracked documentation or public issues.
