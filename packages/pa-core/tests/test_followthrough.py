from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo


def task(id, **kw):
    return dict(id=id, title=id, status='To Do', priority='High', next_action='Read evidence', owner='Assistant', **kw)


def test_selection_keeps_waiting_and_started_and_excludes_closed_parked():
    from pa_core.followthrough import select_actions
    rows=[task('amp'),task('wait'),task('old', due_date='2026-10-01'),task('gone'),task('park')]
    rows[0]['status']='In Progress'; rows[1].update(status='Waiting',next_review='2026-11-25')
    rows[3]['status']='Discarded';rows[4]['lane']='🅿️ Parked'
    r=select_actions(rows, '2026-11-25T08:30:00+00:00')
    assert {t['id'] for t in r['actions']}=={'amp','wait'}
    assert [t['id'] for t in r['review_queue']]==['old']


def test_deadline_beats_priority_and_selected_persists():
    from pa_core.followthrough import select_actions
    rows=[task('focus'),task('deadline',due_date='2026-11-27',deadline_basis='External'),task('other')]
    r=select_actions(rows,'2026-11-25T08:30:00+00:00',state={'selected_task':'focus'})
    assert [x['id'] for x in r['actions']][:2]==['deadline','focus']


def test_snooze_weekends_illness_and_changed_approach():
    from pa_core.followthrough import select_actions
    rows=[task('work',project='Day Job'),task('home',project='Family'),task('later',next_review='2026-12-01')]
    r=select_actions(rows,'2026-11-28T08:30:00+00:00',energy='low',state={'tasks':{'home':{'stalled':2}}})
    assert len(r['actions'])==1 and r['actions'][0]['id']=='home'
    assert r['actions'][0]['change_approach']


def test_unavailable_is_not_empty():
    from pa_core.followthrough import get_followthrough
    with patch('pa_notion.tasks.list_tasks',side_effect=RuntimeError('offline')):
        r=get_followthrough()
    assert r['errors'] and not r['actions']


def test_created_is_not_completed():
    from pa_core.context import _count_completed
    with patch('pa_core.context.get_events',return_value=[{'category':'task','action':'created','summary':'capture'}]):
        assert _count_completed('2026-11-25',1)==0


def test_deduplicated_task_completions():
    from pa_core.context import _count_completed
    e={'category':'task','action':'completed','summary':'done','details':{'task_id':'a'}}
    with patch('pa_core.context.get_events',return_value=[e,e]):
        assert _count_completed('2026-11-25',7)==1


def test_record_checkin_idempotent_and_progress_resets(tmp_path):
    from pa_core.followthrough import record_checkin
    with patch('pa_core.config.PA_ROOT',tmp_path):
        a=record_checkin('a','2026-11-25-am',progress='2026-11-20')
        b=record_checkin('a','2026-11-25-am',progress='2026-11-20')
        assert a==b
        c=record_checkin('a','2026-11-25-pm',progress='2026-11-20')
        assert c['tasks']['a']['stalled']==2
        d=record_checkin('a','2026-11-26-am',progress='2026-11-26')
        assert d['tasks']['a']['stalled']==0


def test_slot_uses_london_dst():
    from pa_core.followthrough import checkin_slot
    assert checkin_slot('2026-07-01T07:30:00+00:00')=='2026-07-01-am'
    assert checkin_slot('2026-11-25T15:30:00+00:00')=='2026-11-25-pm'


def test_render_read_only():
    from pa_core.followthrough import get_followthrough
    with patch('pa_notion.tasks.list_tasks',return_value=[task('a')]),patch('pa_core.state.set_state') as w:
        get_followthrough();get_followthrough()
        w.assert_not_called()


def test_cli_followthrough_is_read_only(capsys):
    from pa_core.cli import main
    result={'actions':[],'errors':[],'review_queue':[],'deadline_conflicts':[]}
    with patch('sys.argv',['pa-core','followthrough','--json']),patch('pa_core.followthrough.get_followthrough',return_value=result),patch('pa_core.followthrough.record_checkin') as write:
        main()
    assert 'actions' in capsys.readouterr().out
    write.assert_not_called()


def test_briefing_uses_shared_selector():
    from pa_core.briefing import _focus_section
    r={'actions':[dict(task('amp'),reason='Chosen commitment',change_approach=False)],'errors':[],'review_queue':[],'deadline_conflicts':[]}
    with patch('pa_core.followthrough.get_followthrough',return_value=r) as get:
        assert 'Read evidence' in '\n'.join(_focus_section())
        get.assert_called_once()


def test_discarded_not_active_flow():
    from pa_notion.flow import compute_snapshot
    assert compute_snapshot([task('x',)],'2026-11-25')['open']==1
    t=task('x');t['status']='Discarded'
    assert compute_snapshot([t],'2026-11-25')['open']==0


def test_notes_update_not_completion():
    from pa_notion.stats import get_task_stats
    with patch('pa_notion.stats.list_tasks',return_value=[dict(task('x'),last_edited_time='2026-11-25')]):
        assert sum(x['count'] for x in get_task_stats('2026-11-25')['completed_last_7d'])==0


def test_stats_use_closure_date_not_last_edit():
    from pa_notion.stats import get_task_stats
    rows=[{'id':'a','status':'Done','closed_at':'2026-09-01','last_edited_time':'2026-11-25','project':'Family'}, {'id':'b','status':'Discarded','project':'Family'}]
    with patch('pa_notion.stats.list_tasks',return_value=rows):
        r=get_task_stats('2026-11-25')
    assert r['active']==0 and sum(r['completed_by_project_7d'].values())==0


def test_external_deadline_separate_from_old_preparation_date():
    from pa_core.followthrough import select_actions
    t=task('phd',due_date='2026-11-24',external_deadline='2026-11-27T16:00:00+00:00',deadline_basis='Personal target',next_review='2026-11-26')
    assert select_actions([t],'2026-11-25T09:00:00+00:00')['actions'][0]['reason']=='External deadline'


def test_legacy_batch_log_is_not_exact_task_count():
    from pa_core.context import _count_completed
    with patch('pa_core.context.get_events',return_value=[{'category':'task','action':'completed','summary':'Closed 25 old tasks'}]):
        assert _count_completed('2026-11-25',1)==0


def test_verified_external_deadline_overrides_unknown_old_target():
    from pa_core.followthrough import select_actions
    row=task('urgent',due_date='2026-10-01',external_deadline='2026-11-24',deadline_basis='Unknown')
    assert select_actions([row],'2026-11-25T08:30:00')['actions'][0]['id']=='urgent'


def test_reconciliation_queue_is_bounded():
    from pa_core.followthrough import select_actions
    rows=[task(str(i),due_date='2026-10-01') for i in range(20)]
    r=select_actions(rows,'2026-11-25T08:30:00')
    assert len(r['review_queue'])==5
    assert r['review_count']==20
