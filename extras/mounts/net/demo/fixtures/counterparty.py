"""The controlled inbox fixture, for regression only. It plays the businesses in market.json: it watches the
mail gateway's outbox directory, and for each mail to one of them it drops a reply into the gateway's inbox
directory with the headers a real mailbox would carry (In-Reply-To and References of the mail's Message-ID,
the sender's address, a message id of its own). Every reply is marked simulated in its text. A real mailbox
later delivers the same shape over IMAP; nothing in any namespace changes.

  python3 counterparty.py --outbox <gateway dir>/out --inbox <gateway dir>/in --market market.json [--week-seconds 15]

Personas answer from their hidden state by week; the clock starts when the fixture starts.
"""
import argparse, email.utils, json, os, re, time

ap = argparse.ArgumentParser()
ap.add_argument('--outbox', required=True); ap.add_argument('--inbox', required=True); ap.add_argument('--market', required=True)
ap.add_argument('--week-seconds', type=float, default=15.0); ap.add_argument('--once', action='store_true')
args = ap.parse_args()
market = json.load(open(args.market))
personas = {p['mailbox'].lower(): p for p in market['personas']}
answered = set()
started = None  # the clock starts at the first message, so slow boots do not advance the story
os.makedirs(args.inbox, exist_ok=True)


def week():
    global started
    if started is None: started = time.monotonic()
    return int((time.monotonic() - started) // args.week_seconds) + 1


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


def deliver(persona, headers, text, n):
    """One reply file in the gateway's inbox, written whole then renamed, as a mail server would hand it over."""
    parent = headers.get('message-id', '').strip()
    mid = email.utils.make_msgid(domain=persona['mailbox'].split('@')[1])
    raw = (f"From: {persona['name']} <{persona['mailbox']}>\r\nTo: {headers.get('from', '')}\r\nSubject: Re: {headers.get('subject', '')}\r\n"
           f"Date: {email.utils.formatdate(localtime=False)}\r\nMessage-ID: {mid}\r\nIn-Reply-To: {parent}\r\nReferences: {parent}\r\n"
           f"MIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{text}\r\n")
    name = f"{int(time.time() * 1000)}-{n}.eml"
    temp = os.path.join(args.inbox, name + '.tmp')
    open(temp, 'w').write(raw); os.rename(temp, os.path.join(args.inbox, name))
    return name


n = 0
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
        n += 1
        written = deliver(persona, headers, text, n)
        print(f'[{week()}] {persona["name"]} replied to {name} as {written}', flush=True)
    if args.once: break
    time.sleep(0.5)
