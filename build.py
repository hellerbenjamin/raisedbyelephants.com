#!/usr/bin/env python3
"""Regenerate the Shows section of index.html from shows.json.

shows.json is the source of truth. This writes two generated regions of
index.html, each fenced by BEGIN/END markers:

  generated:shows   the .show markup in the shows list
  generated:events  MusicEvent JSON-LD for upcoming shows, in <head>

Both are emitted as static HTML so every crawler sees them without running JS.

Usage:  python3 build.py [--check]

  --check  exit non-zero if index.html is out of date instead of writing it
"""

import datetime as dt
import html
import io
import json
import re
import sys

INDEX = 'index.html'
DATA = 'shows.json'
SITE = 'https://raisedbyelephants.com/'
MONTH_ABBR = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
              'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']


def nth_sunday(year, month, n):
    d = dt.date(year, month, 1)
    return d + dt.timedelta(days=(6 - d.weekday()) % 7 + (n - 1) * 7)


def alaska_offset(date):
    """AKDT (-08:00) from the 2nd Sunday in March to the 1st Sunday in November."""
    start = nth_sunday(date.year, 3, 2)
    end = nth_sunday(date.year, 11, 1)
    return '-08:00' if start <= date < end else '-09:00'


def display_title(show):
    """venue [w/ <with>] [• <note>] — the heading shown on the page."""
    title = show['venue']
    if show.get('with'):
        title += ' w/ ' + show['with']
    if show.get('note'):
        title += ' • ' + show['note']
    return title


def render_shows(shows):
    out = []
    for s in shows:
        date = dt.date.fromisoformat(s['date'])
        attrs = ' data-date="%s"' % s['date']
        if s.get('time'):
            attrs += ' data-time="%s"' % s['time']
        tickets = s.get('tickets')
        if tickets:
            attrs += ' data-tickets="%s"' % html.escape(tickets, quote=True)
            meta = ('                    <a href="%s" target="_blank" rel="noopener"\n'
                    '                       class="btn ticket-btn">Tickets</a>'
                    % html.escape(tickets, quote=True))
        else:
            meta = '                    <span class="free-badge">Free</span>'

        out.append(
            '            <div class="show"%s>\n'
            '                <div class="show-date">\n'
            '                    %s<br>%d\n'
            '                </div>\n'
            '                <div class="show-details">\n'
            '                    <h4>%s</h4>\n'
            '                    <p>%s</p>\n'
            '                </div>\n'
            '                <div class="show-meta">\n'
            '%s\n'
            '                </div>\n'
            '            </div>'
            % (attrs, MONTH_ABBR[date.month - 1], date.day,
               # quote=False: apostrophes belong in text content ("Van's", not "Van&#x27;s")
               html.escape(display_title(s), quote=False).replace('•', '&bull;'),
               html.escape(s['city'], quote=False), meta))
    return '\n'.join(out)


def render_events(shows, today):
    events = []
    for s in shows:
        date = dt.date.fromisoformat(s['date'])
        if date < today:
            continue  # Google only surfaces future events
        start = s['date']
        if s.get('time'):
            start = '%sT%s:00%s' % (s['date'], s['time'], alaska_offset(date))

        place = {'@type': 'Place', 'name': s['venue']}
        m = re.match(r'^(.+),\s*([A-Z]{2})$', s.get('city', ''))
        if m:
            place['address'] = {
                '@type': 'PostalAddress',
                'addressLocality': m.group(1).strip(),
                'addressRegion': m.group(2),
                'addressCountry': 'US',
            }

        # No validFrom: it would embed the build date, making output churn daily and
        # `--check` fail on every push. Output must only change when the shows do.
        offer = {
            '@type': 'Offer',
            'url': s.get('tickets') or SITE + '#shows',
            'priceCurrency': 'USD',
            'availability': 'https://schema.org/InStock',
        }
        if not s.get('tickets'):
            offer['price'] = '0'

        events.append({
            '@context': 'https://schema.org',
            '@type': 'MusicEvent',
            'name': 'Raised by Elephants at ' + s['venue'],
            'startDate': start,
            'eventStatus': 'https://schema.org/EventScheduled',
            'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
            'location': place,
            'performer': {'@id': SITE + '#band'},
            'organizer': {'@type': 'MusicGroup', 'name': 'Raised by Elephants', 'url': SITE},
            'image': SITE + 'images/raised-by-elephants-logo-400.png',
            'offers': offer,
        })

    if not events:
        return '    <!-- no upcoming shows -->'
    body = json.dumps(events, indent=2, ensure_ascii=False)
    body = '\n'.join('    ' + line for line in body.splitlines())
    return ('    <script type="application/ld+json">\n%s\n    </script>' % body)


def splice(text, region, replacement):
    begin, end = '<!-- BEGIN generated:%s -->' % region, '<!-- END generated:%s -->' % region
    pattern = re.compile(re.escape(begin) + r'.*?' + re.escape(end), re.S)
    if not pattern.search(text):
        sys.exit('error: markers for "%s" not found in %s' % (region, INDEX))
    return pattern.sub(lambda _: '%s\n%s\n%s' % (begin, replacement, end), text, count=1)


def main():
    check = '--check' in sys.argv[1:]
    data = json.load(io.open(DATA, encoding='utf-8'))
    shows = sorted(data['shows'], key=lambda s: (s['date'], s.get('time', '')))
    today = dt.date.today()

    original = io.open(INDEX, encoding='utf-8').read()
    updated = splice(original, 'shows', render_shows(shows))
    updated = splice(updated, 'events', render_events(shows, today))
    updated = re.sub(r'(<h2 class="section-title">)[^<]*(</h2>\s*<button class="past-shows-toggle")',
                     lambda m: m.group(1) + html.escape(data['season']) + m.group(2), updated, count=1)

    upcoming = sum(1 for s in shows if dt.date.fromisoformat(s['date']) >= today)
    if check:
        if updated != original:
            sys.exit('index.html is out of date with shows.json — run: python3 build.py')
        print('index.html is up to date (%d shows, %d upcoming)' % (len(shows), upcoming))
        return
    if updated == original:
        print('no changes (%d shows, %d upcoming)' % (len(shows), upcoming))
        return
    io.open(INDEX, 'w', encoding='utf-8').write(updated)
    print('wrote %s: %d shows, %d upcoming events' % (INDEX, len(shows), upcoming))


if __name__ == '__main__':
    main()
