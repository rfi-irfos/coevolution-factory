import sys; sys.path.insert(0,'.')
import runtime

def _seed(slug, kind):
    # isolate: each test seeds its own clean jobs dict so the two tests
    # don't contend for the same center via the shared module-global state.
    runtime.state.setdefault('jobs', {}).clear()
    runtime.state['jobs']['run_'+kind] = {
        'center': slug, 'status': 'running', 'created': 1,
        'text': 'x', 'panel': ['a'], 'result': None, 'error': None, 'kind': kind}

def test_kind_passthrough():
    _seed('gdpr-guard', 'discuss')
    assert runtime.state['jobs']['run_discuss']['kind'] == 'discuss'

def test_active_job_exposes_kind():
    _seed('gdpr-guard', 'develop')
    aj = runtime._active_job_for('gdpr-guard')
    assert aj is not None and aj.get('kind') == 'develop'
