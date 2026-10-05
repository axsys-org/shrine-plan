"""Bounded, owner-derived spatial evidence. Proximity is never write authority."""
import math

CHANNELS = {'x', 'y', 'width', 'height', 'angle', 'row', 'label', 'text', 'colour', 'value'}

def context(scene, interaction, selected=None):
    if not isinstance(interaction, dict):
        interaction = {}
    workspace = interaction.get('workspace') or None
    blocks = [b for b in scene.get('blocks', []) if not b.get('archived') and (b.get('workspace') or None) == workspace]
    by_id = {b['id']: b for b in blocks}
    target = by_id.get(interaction.get('target')) or by_id.get(selected)
    point = interaction.get('point')
    valid_point = isinstance(point, dict) and all(isinstance(point.get(k), (int, float)) and not isinstance(point.get(k), bool) and math.isfinite(point[k]) and abs(point[k]) <= 100000 for k in ('x', 'y'))
    if not valid_point:
        point = None
    def rect(b):
        r = b.get('rect', {})
        return {k: r.get(k, 0) for k in ('x', 'y', 'w', 'h')}
    def describe(b):
        return {'id': b['id'], 'revision': b.get('revision'), 'part': b.get('shape') or b.get('part'), 'label': next((c.get('text', '') for c in b.get('content', []) if c.get('kind') == 'text'), ''), 'rect': rect(b), 'parent': b.get('parent'), 'collection': b.get('nativeCollection'), 'mapping': b.get('mapping', {})}
    containers = []
    if point:
        for b in blocks:
            r = rect(b)
            if b.get('part') == 'frame' and r['x'] <= point['x'] <= r['x']+r['w'] and r['y'] <= point['y'] <= r['y']+r['h']:
                containers.append(b)
        containers.sort(key=lambda b: rect(b)['w']*rect(b)['h'])
    parent = by_id.get(target.get('parent')) if target else (containers[0] if containers else None)
    if not point and target:
        r = rect(target)
        point = {'x': r['x']+r['w']/2, 'y': r['y']+r['h']/2}
    def distance(b):
        r = rect(b)
        return math.hypot(max(r['x']-point['x'], 0, point['x']-r['x']-r['w']), max(r['y']-point['y'], 0, point['y']-r['y']-r['h']))
    nearby = sorted((b for b in blocks if b is not target and b is not parent and point and distance(b) <= 320), key=lambda b: (distance(b), b['id']))[:8]
    channel = interaction.get('channel') if target and interaction.get('channel') in CHANNELS else None
    return {'workspace': workspace, 'gesture': interaction.get('gesture') if interaction.get('gesture') in ('drop', 'point', 'ask') else 'ask', 'target': describe(target) if target else None, 'channel': channel, 'container': describe(parent) if parent else None, 'nearby': [describe(b) for b in nearby], 'authority': 'Spatial evidence suggests alternatives only; it never activates a binding or authorizes a write.'}
