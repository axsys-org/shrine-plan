"""No build step or external services. Eden --check runs these live API checks."""
import json
import urllib.error
import urllib.request


def check(url, node, timeout):
    def get(path):
        with urllib.request.urlopen(url + '/pathways' + path, timeout=timeout) as response:
            return response.read()

    def post(payload, status=200):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        request = urllib.request.Request(url + '/pathways/save', body,
                                        {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                assert response.status == status
                response.read()  # Eden returns a committed/back HTML acknowledgement.
                return json.loads(get('/state'))
        except urllib.error.HTTPError as error:
            assert error.code == status, (error.code, error.read())

    assert b'Pathways' in get('')
    atlas = json.loads(get('/atlas.json'))
    assert atlas['id'] == 'redox-folate-clock-v1'
    for path in ('/style.css', '/app.js', '/model.mjs'):
        assert get(path)
    initial = json.loads(get('/state'))
    case = dict(id='http-check', title='Namespace test', observations=[
        dict(id='late_sleep', state='present', note='Example only'),
        dict(id='inattention', state='absent', note='Preserve absence')],
        hypotheses=['circadian_delay'], custom=dict(statement='', targets=[],
        direction='unspecified', rationale=''), notes='Saved in Shrine')
    request = dict(atlas=atlas['id'], revision=initial['revision'], receipt='check-one', cases=[case])
    saved = post(request)
    assert saved['receipt'] == 'check-one' and saved['cases'] == [case], saved
    assert int(saved['revision']) == int(initial['revision']) + 1
    assert json.loads(get('/state')) == saved, 'Read must observe committed state'
    stale = post(dict(request, receipt='stale', cases=[]))
    assert stale == saved, 'Stale writes must not change state'
    post(b'{', 400)
    post(json.dumps(request).encode() + b' trailing', 400)
    post(dict(request, cases=[dict(case, hypotheses=['unknown', 'unknown'])]), 400)
    post(dict(request, cases=[dict(case, hypotheses=['unknown'])]), 400)
    post(dict(request, cases=[dict(case, observations=[dict(id='unknown', state='present', note='')])]), 400)
    post(dict(request, cases=[dict(case, custom=dict(case['custom'], statement='Test', targets=['unknown']))]), 400)
    post(dict(request, cases=[dict(case, custom=dict(case['custom'], targets=['gsr']))]), 400)
    post(dict(request, cases=[case, case]), 400)
    post(dict(request, cases=[dict(case, observations=[dict(id='late_sleep', state='diagnosed', note='')])]), 400)
    post(dict(request, cases=[dict(case, notes=123)]), 400)
    post(dict(request, atlas='other-atlas'), 400)
    assert json.loads(get('/state')) == saved, 'Rejected input must not mutate cases'
    # Leave the fresh check world as it was, using the same revision protocol.
    restored = post(dict(atlas=atlas['id'], revision=saved['revision'], receipt='check-restore', cases=initial['cases']))
    assert restored['cases'] == initial['cases']
    print('PATHWAYS-HTTP-PASS: assets, namespace save/read, stale-write protection, invalid input')
