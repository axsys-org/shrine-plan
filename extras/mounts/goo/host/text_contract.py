"""Validate additive text fields before comparing with historical string-only oracles."""

def plain(runs):
    assert isinstance(runs, list), 'textRuns must be an array'
    result = []
    for run in runs:
        assert set(run) == {'myth', 'lang'} and run['myth'] == {}, 'unsupported descriptor in legacy comparison'
        assert set(run['lang']) == {'en'} and set(run['lang']['en']) == {'txt'}, 'unsupported language'
        text = run['lang']['en']['txt']
        assert isinstance(text, str), 'run text must be a string'
        result.append(text)
    return ''.join(result)


def legacy_text_fields(value):
    """Only remove checked additions; never hide changed legacy field values."""
    if not isinstance(value, dict):
        return value
    value = dict(value)
    if 'textRuns' in value:
        assert plain(value['textRuns']) == value.get('payload', value.get('text')), 'text projection differs'
        del value['textRuns']
    if 'runLines' in value:
        lines = value['runLines']
        assert (None if lines is None else [plain(runs) for runs in lines]) == value['lines'], 'wrapped projection differs'
        del value['runLines']
    if 'runs' in value and {'text', 'baseline', 'box'} <= value.keys():
        runs = value['runs']
        assert ''.join(r['text'] for r in runs) == value['text'], 'fragment projection differs'
        x = value['textX']
        for run in runs:
            assert run['myth'] == {} and run['lang'] == 'en', 'unsupported fragment'
            assert abs(run['textX'] - x) < 1e-6 and run['baseline'] == value['baseline'], 'fragment origin differs'
            x += run['box']['width']
        assert abs(x - value['textX'] - value['box']['width'] + value['prefixAdvance']) < 1e-6, 'fragment widths differ'
        del value['runs']
    return value


def legacy_text_projection(value):
    value = legacy_text_fields(value)
    if isinstance(value, dict):
        return {k: legacy_text_projection(v) for k, v in value.items()}
    if isinstance(value, list):
        return [legacy_text_projection(v) for v in value]
    return value
