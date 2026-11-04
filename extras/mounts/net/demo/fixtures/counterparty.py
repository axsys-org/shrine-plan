"""The controlled inbox fixture, for regression only. It plays the businesses in market.json: it watches the
host's outbox directory, and for each mail to one of them it posts a reply to the host's inbound hook with
the headers a real provider would carry (In-Reply-To of the mail's Message-ID, the sender's address, a
message id of its own). Every reply is marked simulated in its text. A real mailbox later posts the same
shape to the same hook; nothing in the namespace changes.

  python3 counterparty.py --outbox <dir> --hook <origin>/hooks/mail/<secret> --market market.json [--week-seconds 15]

Personas answer from their hidden state by week; the clock starts when the fixture starts.
"""
import argparse, json, os, re, sys, time, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument('--outbox', required=True); ap.add_argument('--hook', required=True); ap.add_argument('--market', required=True)
ap.add_argument('--week-seconds', type=float, default=15.0); ap.add_argument('--once', action='store_true')
args = ap.parse_args()
market = json.load(open(args.market))
personas = {p['mailbox'].lower(): p for p in market['personas']}
answered = set()
started = time.monotonic()


def week(): return int((time.monotonic() - started) // args.week_seconds) + 1


def state_of(p):
    """The persona's state this week: the base, then every story step whose week has come."""
    state = dict(p.get('state', {}))
    for step in p.get('story', []):
        if step.get('week', 0) <= week(): state.update(step.get('set', {}))
    return state


replies = {}


def reply_text(p, state, subject, body):
    if state.get('silent'): return None
    lines = [f"Hello, {p['name']} here."]
    nth = replies.get(p['mailbox'], 0); replies[p['mailbox']] = nth + 1
    if not state.get('in_business', True):
        lines.append("We have closed the business and are no longer taking orders.")
    else:
        asked_price = re.search(r'\$?(\d+(?:\.\d+)?)\s*(?:/|per)\s*unit', body)
        offer = state.get('price')
        # the first message gets the list price; a later message naming a price at or above the floor is accepted
        if nth > 0 and asked_price and offer is not None and float(asked_price.group(1)) < float(offer) and state.get('floor') is not None and float(asked_price.group(1)) >= float(state['floor']):
            lines.append(f"We can offer ${asked_price.group(1)}/unit for a recurring arrangement, valid for 30 days, subject to capacity.")
        elif offer is not None:
            lines.append(f"We can supply what you describe. Our current price is ${offer}/unit.")
        if state.get('lead_days'): lines.append(f"Lead time is {state['lead_days']} days.")
        if state.get('capacity'): lines.append(f"Capacity: {state['capacity']}.")
        if state.get('availability'): lines.append(f"Availability: {state['availability']}.")
    lines.append("(This reply is simulated by the regression fixture.)")
    return "\n".join(lines)


def mails():
    out = []
    for name in sorted(os.listdir(args.outbox)):
        if not name.endswith('.eml'): continue
        text = open(os.path.join(args.outbox, name), errors='replace').read(); head, _, body = text.partition('\n\n')
        headers = {k.strip().lower(): v.strip() for k, v in (l.split(':', 1) for l in head.splitlines() if ':' in l)}
        out.append((name, headers, body))
    return out


def post(payload):
    req = urllib.request.Request(args.hook, json.dumps(payload).encode(), {'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)


while True:
    for name, headers, body in mails():
        marker = os.path.join(args.outbox, name + '.answered')
        if name in answered or os.path.exists(marker): continue
        to = headers.get('to', '').lower()
        persona = next((p for mb, p in personas.items() if mb in to), None)
        answered.add(name); open(marker, 'w').close()
        if not persona: continue
        state = state_of(persona)
        text = reply_text(persona, state, headers.get('subject', ''), body)
        if text is None:
            print(f'[{week()}] {persona["name"]}: silent on {name}', flush=True); continue
        payload = {'from': persona['mailbox'], 'from_name': persona['name'], 'to': headers.get('from', ''), 'subject': 'Re: ' + headers.get('subject', ''),
                   'text': text, 'message_id': f'<{int(time.time() * 1000)}.{persona["mailbox"]}>', 'in_reply_to': headers.get('message-id', ''),
                   'authenticated': 'claimed', 'simulated': True}
        try:
            answer = post(payload); print(f'[{week()}] {persona["name"]} replied to {name}: {answer}', flush=True)
        except Exception as e:
            print(f'[{week()}] {persona["name"]}: hook refused {name}: {e}', flush=True); answered.discard(name)
    if args.once: break
    time.sleep(0.5)
