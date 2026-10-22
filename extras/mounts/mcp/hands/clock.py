"""The clock hand: the only "today" there is. Once a day it writes /clock {day, timezone}; cells point at it, live or
pinned. Config: /agent/hands/clock {timezone} (an IANA name, default UTC); --timezone overrides.

    python3 clock.py <base> [--node 0x11] [--timezone Europe/Berlin] [--once]
"""
import datetime
import importlib.util
import os
import zoneinfo

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand = _hand.World, _hand.Hand


def today(now, timezone):
    """The plug: the day a clock reading falls on, in a timezone."""
    return datetime.datetime.fromtimestamp(now, zoneinfo.ZoneInfo(timezone)).date().isoformat()


class Clock(Hand):
    name = 'clock'
    every = 60.0

    def tick(self, now):
        timezone = self.setting('timezone') or 'UTC'
        day = today(now, timezone)
        path = '/' + self.w.node + '/clock'
        current = self.w.read(path, 'x').get('properties') or {}
        if current.get('/day') == day:
            return 0
        self.write([{'path': path, 'slots': {'day': day, 'timezone': timezone}}])
        self.log(f'clock: {day} ({timezone})')
        return 1


if __name__ == '__main__':
    _hand.run(Clock, settings=('timezone',))
