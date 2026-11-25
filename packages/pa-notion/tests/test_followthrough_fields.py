from unittest.mock import patch,MagicMock

def test_extract_fields():
    from pa_notion.tasks import _extract_task
    p={'id':'a','properties':{'Notes':{'rich_text':[{'plain_text':'context'}]},'Next Action':{'rich_text':[{'plain_text':'Call'}]},'Next Owner':{'select':{'name':'User'}},'Next Review':{'date':{'start':'2026-11-26'}},'Lane':{'select':{'name':'🔥 Live'}}}}
    t=_extract_task(p)
    assert (t['next_action'],t['owner'],t['next_review'],t['notes'],t['lane'])==('Call','User','2026-11-26','context','🔥 Live')


def test_schema_and_validation():
    from pa_notion.followthrough import build_properties
    p=build_properties({'next_action':'Read','owner':'Assistant','next_review':'2026-11-25','outcome':'Submitted'})
    assert p['Next Owner']['select']['name']=='Assistant'
    import pytest
    with pytest.raises(ValueError):build_properties({'owner':'guess'})


def test_repeated_closure_preserves_date():
    from pa_notion.tasks import update_task
    p={'id':'a','properties':{'Task':{'title':[{'plain_text':'A'}]},'Status':{'select':{'name':'Done'}},'Closed At':{'date':{'start':'2026-10-01'}},'Closure Reason':{'select':{'name':'Completed'}}}}
    with patch('pa_notion.tasks.NotionClient') as cls:
        cls.return_value.get_page.return_value=p
        update_task('a',status='Done')
        assert 'Closed At' not in cls.return_value.update_page.call_args.args[1]


def test_verification_accepts_notion_normalised_timestamp():
    from pa_notion.tasks import update_task
    p={'id':'a','properties':{'Next Review':{'date':{'start':'2026-11-26T08:30:00.000+00:00'}}}}
    with patch('pa_notion.tasks.NotionClient') as cls:
        cls.return_value.get_page.return_value=p
        assert update_task('a',next_review='2026-11-26T08:30:00+00:00')['id']=='a'
