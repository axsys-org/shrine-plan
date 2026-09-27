"""Read-only physical Canvas iCalendar adapter. No cookies, credentials or Canvas writes."""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo
import hashlib, json, re
from icalendar import Calendar

TZ = ZoneInfo('America/New_York')
PRIVATE = Path.home()/'.local/share/shrine/canvas'
MAX_BYTES = 4*1024*1024

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

def fetch():
    config = json.loads((PRIVATE/'connection.json').read_text())
    address = config['feed_url']
    u = urlparse(address)
    if u.scheme != 'https' or u.netloc != 'sit.instructure.com' or not u.path.startswith('/feeds/calendars/'):
        raise ValueError('Configure the official Stevens Canvas calendar feed.')
    with build_opener(NoRedirect).open(Request(address, headers={'Accept':'text/calendar'}), timeout=25) as r:
        data = r.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES or not data.lstrip().startswith(b'BEGIN:VCALENDAR'):
        raise ValueError('Canvas did not return a supported calendar; previous observations were preserved.')
    return data

def epoch(value):
    if isinstance(value, datetime):
        return int((value if value.tzinfo else value.replace(tzinfo=TZ)).timestamp())
    return int(datetime.combine(value, time.min, TZ).timestamp())

def parse(data):
    calendar = Calendar.from_ical(data)
    records=[]
    for e in calendar.walk('VEVENT'):
        if 'UID' not in e or 'DTSTART' not in e:
            raise ValueError('Calendar item lacks an identity or start date.')
        if 'RRULE' in e or 'RECURRENCE-ID' in e:
            raise ValueError('Recurring feed structure requires an adapter update; no partial refresh applied.')
        uid=str(e['UID']); url=str(e.get('URL',''))
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.netloc!='sit.instructure.com':
            raise ValueError('Unexpected Canvas item address.')
        context=parse_qs(parsed.query).get('include_contexts',[''])[0]
        course=int(context[7:]) if re.fullmatch(r'course_\d+',context) else 0
        kind='assignment' if uid.startswith('event-assignment-') else 'event'
        summary=str(e.get('SUMMARY','Untitled'))
        title, _, course_name = summary.rpartition(' [')
        if not title: title=summary
        else: course_name=course_name.rstrip(']')
        start=e.decoded('DTSTART'); all_day=not isinstance(start,datetime)
        localdate=(start.astimezone(TZ).date() if not all_day and start.tzinfo else start.date() if not all_day else start)
        end=e.decoded('DTEND') if 'DTEND' in e else start
        # A DATE has no due time. Use the next midnight only as a date-passed boundary,
        # never present it as an exact deadline.
        boundary=epoch(localdate+timedelta(days=1)) if all_day and kind=='assignment' else epoch(start)
        record={'uid':uid,'kind':kind,'title':title,'course_id':course,'course_name':course_name,
                'url':url,'due_date':localdate.isoformat(),'due_epoch':boundary,
                'start_epoch':epoch(start),'end_epoch':epoch(end),'due_precision':'date' if all_day else 'instant',
                'calendar_status':str(e.get('STATUS','')),'sequence':int(e.get('SEQUENCE',0))}
        if re.fullmatch(r'event-assignment-\d+',uid) and course:
            record['canvas_id']=int(uid.removeprefix('event-assignment-'))
            record['url']=f'https://sit.instructure.com/courses/{course}/assignments/{record["canvas_id"]}'
        records.append(record)
    if len({r['uid'] for r in records})!=len(records):raise ValueError('Duplicate calendar identity; preserve earlier snapshot.')
    return records

def archive(data):
    sha=hashlib.sha256(data).hexdigest()
    target=PRIVATE/'artifacts'/f'{sha}.ics';target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if not target.exists():target.write_bytes(data);target.chmod(0o600)
    return {'sha256':sha,'path':str(target),'bytes':len(data)}
