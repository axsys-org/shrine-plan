#!/usr/bin/env python3
"""Exercise compiled matrix constructions through the real native action route.

Only use a disposable native-material world. This is native/HTTP evidence, not
a browser or usability test. No application implementation is supplied here.
"""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class Raster(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.samples = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'canvas' and 'data-grove-raster' in attrs:
            self.width, self.height = int(attrs['width']), int(attrs['height'])
            self.samples = json.loads(attrs['data-grove-raster'])


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--world', type=Path, required=True)
parser.add_argument('--port', type=int, required=True)
args = parser.parse_args()
world = args.world.resolve()
if not world.name.startswith('grove-native-material-'):
    raise SystemExit('Use a disposable native-material development world.')
authority = (world / 'src/medium-authority').read_text()
results, timings = [], []
root = '/0x11/app/material'


def call(operation, body, event=''):
    encoded = urllib.parse.urlencode(dict(credential=authority, principal='administrator',
        operation=operation, expected='0', event=event, body=json.dumps(body))).encode()
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/medium-native', encoded, timeout=120) as response:
            status, value = response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        status, value = error.code, json.loads(error.read())
    timings.append(dict(operation=operation, status=status, ms=(time.perf_counter()-started)*1000))
    return status, value


def check(name, passed, evidence=None):
    results.append(dict(name=name, passed=bool(passed), evidence=evidence))
    print(('PASS ' if passed else 'FAIL ') + name, flush=True)
    if not passed:
        raise AssertionError((name, evidence))


def frame(subject):
    code, value = call('native/frame', dict(subject=subject, viewport=[]))
    if code != 200:
        raise AssertionError(('frame', code, value))
    raster = Raster(value['html'])
    if raster.samples is None:
        raise AssertionError('Native presentation did not produce raster samples.')
    return value, raster


def parameters(x, y, width, height):
    return [dict(slot='/'+key, kind='natural', value=str(value))
            for key, value in dict(x=x, y=y, width=width, height=height).items()]


def operate(subject, key, *, params=None, arguments=None, captured=None, operation='native/act', prior=''):
    f = captured or frame(subject)[0]
    event = uuid.uuid4().hex
    code, value = call(operation, dict(subject=subject, viewport=[], basis=f['basis'],
        key=key, parameters=params or [], arguments=arguments or [], prior=prior), event)
    return code, value, event


def paint(subject, raster, points, captured=None):
    return operate(subject, '/pixel', captured=captured,
        params=parameters(*points[0], raster.width, raster.height),
        arguments=[dict(slot='/points', kind='points',
                        value=[dict(x=str(x), y=str(y)) for x, y in points])])


try:
    image, cells = root+'/image_surface', root+'/cellular_surface'
    initial, raster = frame(image)
    check('native image presentation exposes a matrix and lazy pixel family',
          len(raster.samples) == raster.width*raster.height and '/pixel' in initial['families'])
    pixel_params = parameters(2, 3, raster.width, raster.height)
    code, detail = call('native/inspect', dict(subject=image, viewport=[], basis=initial['basis'],
        key='/pixel', parameters=pixel_params))
    check('pixel resolves to the original native matrix with a typed position',
          code == 200 and detail['occurrence']['focus']['subject'] == root+'/image'
          and detail['occurrence']['slot'] == '/matrix' and detail['occurrence']['typed_selection'], detail)
    code, result, paint_event = paint(image, raster, [(2, 3), (6, 3)], initial)
    check('native pointer action paints the original matrix', code == 200, result)
    painted_frame, painted = frame(image)
    check('native interpolation fills the stroke and preserves its neighbors',
          all(painted.samples[3*raster.width+x] == 2835772 for x in range(2, 7))
          and painted.samples[3*raster.width+1] == raster.samples[3*raster.width+1]
          and painted.samples[4*raster.width+2] == raster.samples[4*raster.width+2])
    code, result, _ = paint(image, raster, [(1, 1)], initial)
    check('old image basis cannot redirect a later stroke', code == 409, result)
    code, result, _ = operate(image, '/pixel', operation='native/undo', prior=paint_event)
    check('native undo restores the stroke without snapshot rollback', code == 200, result)
    check('undo preserves the complete original matrix', frame(image)[1].samples == raster.samples)
    code, result, invert_event = operate(image, '/invert')
    check('native transform commits', code == 200, result)
    check('native transform changes the actual samples',
          frame(image)[1].samples == [16777215 - value for value in raster.samples])
    code, result, _ = operate(image, '/invert', operation='native/undo', prior=invert_event)
    check('transform reverses through the same native action route', code == 200, result)
    code, result, transpose_event = operate(image, '/transpose')
    check('native transpose commits', code == 200, result)
    transposed = frame(image)[1]
    check('transpose changes geometry and reorders the actual native samples',
          (transposed.width, transposed.height) == (raster.height, raster.width)
          and transposed.samples == [raster.samples[y*raster.width+x]
                                     for x in range(raster.width) for y in range(raster.height)])
    code, result, _ = operate(image, '/transpose', operation='native/undo', prior=transpose_event)
    check('transpose undo restores the original matrix geometry',
          code == 200 and frame(image)[1].samples == raster.samples, result)
    code, result, _ = operate(image, '/crop')
    check('native selection mode is editable state', code == 200, result)
    code, result, crop_event = paint(image, raster, [(2, 3), (4, 5)])
    check('native crop changes matrix geometry', code == 200, result)
    crop_frame, crop = frame(image)
    expected = [raster.samples[y*raster.width+x] for y in range(3, 6) for x in range(2, 5)]
    check('crop retains the selected original region', (crop.width, crop.height, crop.samples) == (3, 3, expected))
    code, result, _ = paint(image, raster, [(2, 1)], crop_frame)
    check('fresh basis with stale geometry is still rejected', code == 422, result)
    code, result, crop_undo = operate(image, '/pixel', operation='native/undo', prior=crop_event)
    check('undo of a geometry change does not resolve the old coordinate in the new geometry', code == 200, result)
    check('geometry undo restores the original matrix', frame(image)[1].samples == raster.samples)
    code, result, crop_redo = operate(image, '/pixel', operation='native/undo', prior=crop_undo)
    check('the inverse remains an exact reversible native change',
          code == 200 and frame(image)[1].samples == expected, result)
    code, result, _ = operate(image, '/pixel', operation='native/undo', prior=crop_redo)
    check('undo chain retains native correspondence across repeated shape changes',
          code == 200 and frame(image)[1].samples == raster.samples, result)
    cell_frame, grid = frame(cells)
    code, result, _ = paint(cells, grid, [(1, 1)])
    check('a second native construction reuses matrix painting', code == 200, result)
    code, result, _ = operate(cells, '/step')
    check('native cellular transition uses the same action boundary', code == 200, result)
    next_grid = frame(cells)[1]
    check('isolated painted cell dies and the seeded pattern evolves',
          next_grid.samples[grid.width+1] == 16777215 and next_grid.samples != grid.samples)
finally:
    (world / 'native-matrix-acceptance.json').write_text(json.dumps(dict(results=results, timings=timings,
        coverage='Real compiled Grove/Foil, native owner, HTTP actions and inspected pixel correspondence. '
                 'No browser, large-region, self-hosting, model-authoring, or usability claim.'), indent=2)+'\n')
