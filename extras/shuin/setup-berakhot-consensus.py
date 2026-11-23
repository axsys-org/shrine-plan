#!/usr/bin/env python3
"""Prepare one consensus study round in Shrine; no provider loop runs in Python.

Agents deliberate and publish ballots through their Shrine tools. --inspect reads
ballots without changing them. Round advancement is an explicit operator action;
this script is not a persistent consensus coordinator.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location('seminar', Path(__file__).with_name('setup-berakhot-swarm.py'))
seminar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seminar)
World = seminar.World
STUDY = '/0x11/app/studies/berakhot_plurality'
IDS = ['plurality_a', 'plurality_b', 'plurality_c', 'plurality_d', 'plurality_e']
MODELS = ['openai/gpt-6.2-astra', 'google/gemini-4-neon', 'openai/gpt-6.2-astra', 'openai/gpt-6.2-sol', 'openai/gpt-6.2-sol']
OPTIONS = {
    'hard_end': 'The Sages deny fulfillment after midnight; Rabban Gamliel permits it until dawn: the underlying endpoint is disputed.',
    'two_deadlines': 'The underlying obligation can still be fulfilled until dawn; midnight is a precautionary deadline. Whether its binding force is itself disputed may remain unresolved.',
    'insufficient_evidence': 'The supplied text does not justify preferring either account yet.'}
RULE = ('All five agents must finish and submit a valid ballot for this round. A substantive option wins '
        'only if it has at least two votes and strictly more votes than every other option. '
        'Ties and an insufficient_evidence lead do not end the study. Preserve minority objections; '
        'a plurality is not unanimity and does not establish historical truth.')


def selection(paths):
    return json.dumps({'version': 1, 'hunts': [json.loads(seminar.selection(p))['hunts'][0] for p in paths]})


def inspect(world, round_number):
    rows = []
    for ident in IDS:
        home = seminar.ROOT + '/' + ident
        agent = world.tool('read', path=home, care='x')
        record = world.tool('read', path=home + f'/workspace/plurality_r{round_number}', care='x')
        raw = record.get('properties', {}).get('/sys/content', '')
        ballot = None
        try:
            ballot = json.loads(raw)
        except (ValueError, TypeError):
            pass
        valid = (isinstance(ballot, dict) and ballot.get('study') == STUDY
                 and ballot.get('round') == round_number and ballot.get('choice') in OPTIONS
                 and isinstance(ballot.get('message_path'), str)
                 and ballot['message_path'].startswith(seminar.CHAT + '/'))
        message = world.tool('read', path=ballot['message_path'], care='x') if valid else {}
        valid = valid and message.get('exists') and bool(message.get('properties', {}).get('/sys/content'))
        inbox = world.tool('read', path=home + '/inbox', care='y', limit=100)
        rows.append({'id': ident, 'status': agent.get('properties', {}).get('/status'),
                     'pending_items': len(inbox.get('children', [])),
                     'ballot': ballot, 'valid': bool(valid), 'reference': record.get('reference'),
                     'message_reference': message.get('reference')})
    counts = {k: sum(row['valid'] and row['ballot']['choice'] == k for row in rows) for k in OPTIONS}
    ordered = sorted(counts, key=counts.get, reverse=True)
    complete = all(row['valid'] and row['status'] == 'idle' and row['pending_items'] == 0 for row in rows)
    winner = (ordered[0] if complete and ordered[0] != 'insufficient_evidence'
              and counts[ordered[0]] >= 2 and counts[ordered[0]] > counts[ordered[1]] else None)
    return {'study': STUDY, 'round': round_number, 'complete': complete,
            'counts': counts, 'winner': winner, 'agents': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://127.0.0.1:8277')
    parser.add_argument('--round', type=int, default=1)
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    world = World(args.server)
    if args.inspect:
        print(json.dumps(inspect(world, args.round), ensure_ascii=False, indent=2))
        return
    if args.round < 1:
        parser.error('Round must be positive')
    if args.round == 1:
        assert not world.tool('read', path=STUDY, care='x')['exists'], 'Study already exists; inspect instead.'
        world.tool('write', path=STUDY, properties={
            '/sys/lede': 'Berakhot — plurality study', '/sys/help': RULE,
            '/sys/content': seminar.QUESTION, '/status': 'preparing', '/round': 1,
            '/options': json.dumps(OPTIONS), '/participants': json.dumps(IDS)})
        for ident, (_, title, _, mandate), model in zip(IDS, seminar.AGENTS, MODELS):
            instructions = f'''You are {title} in a new plurality study of Berakhot 2a.
Question: {seminar.QUESTION}
Your initial mandate: {mandate}
Your mandate is a starting position, not an instruction to keep believing it against evidence.
Read the shared discussion and primary text already included in the namespace bundle.
Distinguish quotations, translation, commentary, and inference. Do not invent sources.
Shared chat: {seminar.CHAT}. Study protocol: {STUDY}.
Use the supplied ballot options exactly; preserve nuances and objections in your rationale.
Do not agree merely to end the run. You may vote insufficient_evidence honestly.
For each round: post one concise contribution, 100–180 words, through the discovered
post_message stencil. Label it “Plurality study · round N · {title}”. Verify its created-path
receipt, then write ONE JSON-text ballot into your own workspace at the requested path.
Include study, round (JSON number), choice, rationale, unresolved, and message_path.
Use namespace_write with slot /sys/content and type text to store the JSON string.
Only after the message and ballot commit may you finish this round. The study ends only
when the operator verifies all five ballots against the stated stopping rule; you cannot
certify consensus alone. Keep deliberation concise so the response fits the token budget.
Do not edit the study controls, other agents, or existing chat messages. No waiting loops.
'''
            world.click('add-agent')
            world.click('create-agent', {'agent_id': ident, 'model': model, 'instructions': instructions,
                'read_dependencies': selection([seminar.TALMUD, STUDY]),
                'write_dependencies': selection([seminar.CHAT]), 'draft': ''})
            assert world.tool('read', path=seminar.ROOT + '/' + ident, care='x')['exists']
            world.tool('write', path=seminar.ROOT + '/' + ident, action='poke', properties={
                '/sys/lede': 'Plurality · ' + title, '/sys/help': mandate})
            print('Created', ident, model, flush=True)
    else:
        prior = inspect(world, args.round - 1)
        assert prior['complete'] and not prior['winner'], 'Continue only a complete, non-winning round.'
    round_path = STUDY + '/round_' + str(args.round)
    assert not world.tool('read', path=round_path, care='x')['exists'], 'Round already queued.'
    records = [
        {'path': STUDY, 'action': 'poke', 'properties': {'/status': 'deliberating', '/round': args.round}},
        {'path': round_path, 'properties': {'/sys/lede': f'Round {args.round}', '/sys/help': RULE, '/status': 'deliberating'}},
        {'path': seminar.CHAT + f'/plurality_round_{args.round}', 'properties': {
            '/sys/lede': f'Plurality study — round {args.round}', '/sys/author': 'Study convenor',
            '/sys/now': int(time.time()), '/sys/content': f'PLURALITY STUDY · ROUND {args.round}\n' +
            seminar.QUESTION + '\n\n' + RULE + '\n\n' + '\n'.join(k + ': ' + v for k, v in OPTIONS.items())}}]
    for ident in IDS:
        home = seminar.ROOT + '/' + ident
        agent = world.tool('read', path=home, care='x')['properties']
        assert agent['/status'] == 'idle', (ident, agent['/status'])
        records.extend([
            {'path': home, 'action': 'poke', 'properties': {'/budget': 16}},
            {'path': home + f'/inbox/plurality_r{args.round}', 'properties': {
                '/sys/lede': f'Plurality ballot — round {args.round}', '/sys/content':
                f'Complete round {args.round}. Review the shared discussion; challenge or revise positions on evidence. '
                f'Post your concise argument, then store your JSON ballot at {home}/workspace/plurality_r{args.round}. '
                f'The study field must equal {STUDY}; round must be {args.round}; choose exactly one of '
                'hard_end, two_deadlines, insufficient_evidence. Include rationale, unresolved objections, '
                'and the exact successfully-created message_path. Do not copy someone else’s vote. '
                'After both commits, end this round; further rounds are scheduled if no plurality emerges.'}}])
    receipt = world.tool('write', records=records)
    assert not receipt.get('refused'), receipt
    print('Queued round', args.round, 'at epoch', receipt['epoch'], flush=True)


if __name__ == '__main__':
    main()
