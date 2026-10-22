"""Exercise native work commands through the real MCP transport."""
import sys
from pathlib import Path

# Direct script execution must not shadow the standard-library http package.
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).parent.resolve():
    sys.path.pop(0)

import importlib.util
from contextlib import closing
import runpy
import time
import uuid

_spec = importlib.util.spec_from_file_location('cooperate_client', Path(__file__).parents[1] / 'client.py')
_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_client)
Client, Refused, ContextLimit, reference = (_client.Client, _client.Refused,
                                           _client.ContextLimit, _client.reference)


def check(base, node, timeout):
    client = Client(base, node, timeout)
    home = '/' + node + '/user/cooperate_check_' + uuid.uuid4().hex[:10]
    document, data, total = home + '/document', home + '/data', home + '/total'
    evidence = home + '/evidence'
    publisher = client.publisher

    def write(path, slots, action='make'):
        return client.tool('write', records=[dict(path=path, slots=slots, action=action)])

    def props(path):
        return client.read(path)['properties']

    def refused(call, reason):
        try:
            call()
        except Refused as error:
            assert reason in str(error), (reason, error.reply)
        else:
            raise AssertionError('Expected refusal: ' + reason)

    summer = client.read('/' + node + '/weft/stdlib/sum')['reference']
    client.tool('write', records=[
        dict(path=document, slots={'sys/lede': 'Cooperation transport fixture'}),
        dict(path=data, slots={}),
        dict(path=data + '/a', slots={'amount': 5}),
        dict(path=data + '/b', slots={'amount': 7}),
        dict(path=evidence, slots={'note': 'first observation'}),
        dict(path=total, slots={'sys/weft': reference(summer),
                               'sys/tack': reference(data, 'y'), 'slot': '/amount'})])
    assert props('/x' + total)['/total'] == '12'
    context = {'data': reference(data, 'y'), 'calculated': reference('/x' + total)}
    first = document + '/work/first'
    stream_file = Path(__file__).parents[2] / 'mcp/tests/stream.py'
    StreamClient = runpy.run_path(str(stream_file))['StreamClient']
    with closing(StreamClient(base, timeout)) as events:
        time.sleep(.2)  # Allow the stream connection to register with its fan-out.
        opened = client.open(document, 'first', 'Inspect these inputs.', context=context)
        event = events.event()
        assert event['epoch'] == opened['epoch'], event
        assert first in event['touched'] and first in event['with'], event
        client.open(document, 'first', 'Inspect these inputs.', context=context)
        sentinel = home + '/after_retry'
        written = write(sentinel, {'value': 1})
        next_event = events.event()
        assert next_event['epoch'] == written['epoch'], next_event
        assert sentinel in next_event['touched'], next_event
    assert props(first)[publisher + '/status'] == 'open'
    assert props('/x' + first + '/context/calculated')['/total'] == '12'
    assert props('/x' + first + '/checks/data')['/unchanged'] == 'true'
    initial = client.read(first)['reference']
    client.open(document, 'first', 'Inspect these inputs.', context=context)
    assert client.read(first)['reference'] == initial
    refused(lambda: client.open(document, 'first', 'Changed payload.', context=context), 'work_id_conflict')

    client.append(first, 'message', 'message', 'Starting from the captured inputs.')
    first_event = first + '/trace/message'
    event_pin = client.read(first_event)['reference']
    client.append(first, 'observation', 'observation', 'Additional evidence.',
                  reply_to=event_pin, context={'note': reference(evidence)},
                  artifact=reference('/x' + total))
    observation = first + '/trace/observation'
    assert props(observation)[publisher + '/reply_to'] == event_pin
    assert props('/x' + observation + '/artifact')['/total'] == '12'
    assert props(first)[publisher + '/sequence'] == '2'
    client.append(first, 'message', 'message', 'Starting from the captured inputs.')
    assert props(first)[publisher + '/sequence'] == '2'
    assert client.read(first_event)['reference'] == event_pin
    refused(lambda: client.append(first, 'message', 'message', 'Overwritten.'), 'work_id_conflict')

    captured = client.read_context(first)
    assert {part['label'] for part in captured['captures']} == {'calculated', 'data'}, captured
    observed = client.read_context(first, event='observation')
    assert observed['captures'][0]['pages'][0]['properties']['/note'] == 'first observation'
    try:
        client.read_context(first, max_nodes=1)
    except ContextLimit:
        pass
    else:
        raise AssertionError('Bounded context must not silently return partial input')

    # Observation captures participate in completion, independently of initial inputs.
    write(evidence, {'note': 'corrected observation'}, 'poke')
    refused(lambda: client.finish(first, 'done', 'Outdated.', artifact=reference('/x' + total)), 'stale_context')
    assert props(first)[publisher + '/status'] == 'open'
    assert not client.read(first + '/result')['exists']
    assert props('/x' + observation + '/context/note')['/note'] == 'first observation'
    write(evidence, {}, 'cull')
    assert props('/x' + observation + '/context/note')['/note'] == 'first observation'

    # Initial snapshots and recorded tool results also survive later source changes.
    write(data + '/a', {'amount': 9}, 'poke')
    assert props('/x' + total)['/total'] == '16'
    assert props('/x' + first + '/context/calculated')['/total'] == '12'
    assert props('/x' + observation + '/artifact')['/total'] == '12'
    assert props('/x' + first + '/checks/data')['/unchanged'] == 'false'

    # A new branch selects fresh inputs; unrelated edits do not invalidate it.
    parent_pin = client.read(first)['reference']
    fresh = document + '/work/fresh'
    client.open(document, 'fresh', 'Continue with fresh inputs.', context=context,
                parent=parent_pin, procedure=summer)
    assert props(fresh)[publisher + '/parent'] == parent_pin
    assert client.read('/x' + fresh + '/context/procedure')['exists']
    client.append(fresh, 'answer', 'output', 'The current total is sixteen.', artifact=reference('/x' + total))
    write(home + '/unrelated', {'note': 'does not affect this work'})
    with closing(StreamClient(base, timeout)) as events:
        time.sleep(.2)
        finished = client.finish(fresh, 'done', 'Complete.', artifact=reference('/x' + total))
        event = events.event()
        assert event['epoch'] == finished['epoch'], event
        assert fresh + '/result' in event['touched'], event
        assert fresh + '/commands/done' in event['with'], event
    assert props(fresh)[publisher + '/status'] == 'complete'
    assert props('/x' + fresh + '/result')['/total'] == '16'
    result_pin = client.read(fresh + '/result')['reference']
    client.finish(fresh, 'done', 'Complete.', artifact=reference('/x' + total))
    assert client.read(fresh + '/result')['reference'] == result_pin
    client.append(fresh, 'answer', 'output', 'The current total is sixteen.', artifact=reference('/x' + total))
    refused(lambda: client.append(fresh, 'late', 'message', 'Late output.'), 'work_not_open')
    refused(lambda: client.finish(fresh, 'done', 'Changed payload.'), 'work_id_conflict')

    # Consume the frozen typed output as the input of another ordinary cell.
    pick = client.read('/' + node + '/weft/stdlib/pick')['reference']
    copied = home + '/result_consumer'
    write(copied, {'sys/weft': reference(pick),
                   'sys/tack': reference('/x' + fresh + '/result'),
                   'from': '/total', 'into': '/copied_total'})
    consumer = client.read('/x' + copied)
    assert consumer['properties']['/copied_total'] == '16', consumer
    write(data + '/a', {'amount': 20}, 'poke')
    assert props('/x' + total)['/total'] == '27'
    assert props('/x' + fresh + '/result')['/total'] == '16'
    assert props('/x' + copied)['/copied_total'] == '16'

    # A direct operational artifact can be rebound independently after completion.
    recipe = document + '/work/recipe'
    client.open(document, 'recipe', 'Retain a reusable cell definition.')
    client.finish(recipe, 'done', 'Cell definition.', artifact=reference(total))
    saved_reference = props(recipe)[publisher + '/artifact']
    definition = client.read(saved_reference)['properties']
    other = home + '/other_data'
    client.tool('write', records=[dict(path=other, slots={}),
                                 dict(path=other + '/a', slots={'amount': 3}),
                                 dict(path=other + '/b', slots={'amount': 4})])
    write(home + '/rebound', {'sys/weft': reference(definition['/sys/weft']),
                              'sys/tack': reference(other, 'y'), 'slot': definition['/slot']})
    assert props('/x' + home + '/rebound')['/total'] == '7'
    assert props('/x' + total)['/total'] == '27'

    # Failed capture creates neither a partial run nor a command receipt.
    refused(lambda: client.open(document, 'missing', 'Missing input.',
                                context={'absent': reference(home + '/absent')}), 'missing_context')
    assert not client.read(document + '/work/missing')['exists']
    print('Cooperation MCP passed: captures, branching trace, retries, stale completion, typed output and reuse', flush=True)


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
