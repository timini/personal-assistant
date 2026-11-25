"""Read-only action selection and explicit, atomic check-in acknowledgements.

Selection never sends, changes tasks, or treats source failures as empty results.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import os
import tempfile
import fcntl

from pa_core.config import get_now, get_user_config

CLOSED = {'Done', 'Discarded'}


def _local(value):
    zone = ZoneInfo(get_user_config().get('timezone', 'Europe/London'))
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return dt.replace(tzinfo=zone) if dt.tzinfo is None else dt.astimezone(zone)


def checkin_slot(now):
    dt = _local(now)
    return dt.date().isoformat() + ('-pm' if (dt.hour, dt.minute) >= (15, 30) else '-am')


def _path():
    from pa_core.config import PA_ROOT
    return PA_ROOT / 'activity' / '.followthrough.json'


def read_state():
    p = _path()
    if not p.exists():
        return {}
    # Corruption must be visible, not silently reset reminder history.
    return json.loads(p.read_text())


def record_checkin(task_id, slot, *, progress='', select=False, snooze_until=None):
    """Acknowledge a delivered prompt once per slot; callers must not log before delivery."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read_state()
        tasks = state.setdefault('tasks', {})
        t = tasks.setdefault(task_id, {'stalled': 0, 'slots': []})
        if select:
            state['selected_task'] = task_id
        if snooze_until is not None:
            _local(snooze_until)
            t['snooze_until'] = snooze_until
        if slot not in t['slots']:
            changed = bool(progress) and progress != t.get('progress', progress)
            t['stalled'] = 0 if changed else t['stalled'] + 1
            t['progress'] = progress
            t['slots'] = (t['slots'] + [slot])[-30:]
        state['last_delivered_slot'] = slot
        fd, name = tempfile.mkstemp(dir=p.parent, prefix='.followthrough-')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(state, f, indent=2)
                f.flush(); os.fsync(f.fileno())
            os.replace(name, p)
        finally:
            if os.path.exists(name): os.unlink(name)
        return state


def select_actions(tasks, now, *, state=None, energy='normal'):
    state = state or {}
    dt = _local(now); today = dt.date().isoformat()
    horizon = (dt.date() + timedelta(days=7)).isoformat()
    candidates, review, conflicts = [], [], []
    for source in tasks:
        t = dict(source)
        if t.get('status') in CLOSED:
            continue
        saved = state.get('tasks', {}).get(t['id'], {})
        due = (t.get('external_deadline') or t.get('due_date') or '')[:10]
        external = (bool(t.get('external_deadline')) or t.get('deadline_basis') == 'External') and bool(due) and due <= horizon
        if t.get('status') == 'Someday' or any(x in t.get('lane', '') for x in ('Parked', 'Someday')):
            if external: conflicts.append(t)
            continue
        if saved.get('snooze_until') and _local(saved['snooze_until']) > dt:
            if external: conflicts.append(t)
            continue
        nr = t.get('next_review', '')
        if nr and _local(nr) > dt and not external:
            continue
        if dt.weekday() >= 5 and t.get('project', '').startswith(('Day Job', 'Line Management')) and not external:
            continue
        if not t.get('next_action') or not t.get('owner') or (due and due < today and t.get('deadline_basis', 'Unknown') == 'Unknown' and not t.get('external_deadline')):
            t['reason'] = 'Reconcile evidence / historical date before repeating work'
            review.append(t)
            continue
        if t.get('status') == 'Waiting' and not nr and not external:
            t['reason'] = 'Waiting without a review date';review.append(t);continue
        t['change_approach'] = saved.get('stalled', 0) >= 2
        t['reason'] = ('External deadline' if external else 'Chosen commitment' if t['id'] == state.get('selected_task') else 'Follow-up due' if nr else 'Next action ready')
        t['_rank'] = (0 if external else 1 if t['id'] == state.get('selected_task') else 2 if nr else 3, due or '9999', {'Urgent':0,'High':1,'Medium':2,'Low':3}.get(t.get('priority'),4), t['id'])
        candidates.append(t)
    candidates.sort(key=lambda t:t['_rank'])
    for t in candidates: t.pop('_rank')
    slot = checkin_slot(now)
    return {'actions': candidates[:1 if energy in ('low','unwell','protect') else 3],
            'review_queue': review[:5], 'review_count': len(review), 'deadline_conflicts': conflicts, 'errors': [],
            'slot': slot, 'already_prompted': state.get('last_delivered_slot') == slot,
            'open_count': sum(t.get('status') not in CLOSED for t in tasks)}


def get_followthrough(*, energy='normal'):
    from pa_notion.tasks import list_tasks
    now = get_now()
    timestamp = now['date'] + 'T' + now['time'] + ':00'
    try:
        return select_actions(list_tasks(), timestamp, state=read_state(), energy=energy)
    except Exception as exc:
        return {'actions': [], 'review_queue': [], 'deadline_conflicts': [], 'errors': [f'Follow-through not checked: {exc}'], 'already_prompted': False}


def render_followthrough(result):
    lines = ["## Next actions"]
    if result['errors']:
        return '\n'.join(lines + result['errors'])
    for t in result['actions']:
        lines.append(f"- {t['title']}: {t['next_action']} — {t['owner']} ({t['reason']})")
        if t['change_approach']:
            lines.append('  Stalled twice: prepare more, reduce the step or ask one blocker question. Do not repeat the same reminder.')
    if not result['actions']: lines.append('No ready action selected; review unresolved evidence before claiming everything is done.')
    if result['review_queue']: lines.append(f"{result.get('review_count', len(result['review_queue']))} records need evidence/next-step reconciliation; do not dump them on the user.")
    if result['deadline_conflicts']: lines.append(f"{len(result['deadline_conflicts'])} parked/snoozed deadline conflicts need a decision; do not reactivate silently.")
    if result.get('already_prompted'): lines.append('This check-in slot was already delivered; suppress duplicate prompts unless new material risk appeared.')
    return '\n'.join(lines)
