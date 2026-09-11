---
name: sync-shows
description: Sync the Shows section from the band's gig Google Sheet — add new gigs, correct dates and set times, then regenerate index.html. Use when asked to update shows, add a gig, fix show dates/times, or reconcile the site with the sheet.
---

# Sync shows from the gig sheet

Data flows one way:

```
Google Sheet  ──(this skill)──>  shows.json  ──build.py──>  index.html
```

**Never hand-edit the shows markup in `index.html`.** It sits between
`<!-- BEGIN generated:shows -->` / `<!-- END generated:shows -->` markers and `build.py`
overwrites it. Same for the `MusicEvent` JSON-LD between the `generated:events` markers.
Edit `shows.json`, then run the build.

The gig sheet is the source of truth for **which shows exist, on what date, at what time**.
`shows.json` is the source of truth for **how a show is presented** — public venue name, city,
ticket link. Sync in that direction; never let one overwrite the other's half.

Sheet: https://docs.google.com/spreadsheets/d/1H4mRoEbsmvMWRXivfjBhjwHnb0WsAYqtu2nsf1ubVwM/edit
File ID: `1H4mRoEbsmvMWRXivfjBhjwHnb0WsAYqtu2nsf1ubVwM`

## Read the sheet

Use `mcp__claude_ai_Google_Drive__read_file_content` with the file ID above.

Columns: `Date | Start Time | Length | Notes | Venue | <one column per member>`

**The member columns are availability tracking, not public data.** They are names with
TRUE/FALSE. Never publish them, never infer a lineup change from them, never mention who was
marked unavailable. Read only Date, Start Time, Length, Notes, Venue.

## shows.json

```json
{
  "date": "2026-09-25",
  "venue": "Odd Man Rush Brewing",
  "time": "19:00",
  "city": "Eagle River, AK",
  "note": "EP Release",
  "with": "Powerplay",
  "tickets": "https://www.eventbrite.com/e/..."
}
```

- `date` (required, `YYYY-MM-DD`) and `venue` (required, the **public** name).
- `time` optional, `HH:MM` 24-hour. Present ⇒ the JSON-LD emits a full timestamp with the
  Alaska offset, which Google prefers. Absent ⇒ date only. Omit it rather than guess.
- `city` renders under the venue and becomes the event's `addressLocality`/`addressRegion`.
- `with` is a co-bill, `note` an occasion. They only affect the displayed heading
  (`Venue w/ With • Note`); the event's `location.name` stays the bare venue.
- `tickets` optional ⇒ renders a **Tickets** button. Absent ⇒ a muted **Free** badge.
- Order doesn't matter; `build.py` sorts by date then time.
- `season` sets the section heading (`2026 Shows`). Update when the season rolls over.

## Matching sheet rows to shows.json

Match on date first, then venue. Venue strings in the sheet are internal shorthand and often
differ from the public name. Known pairs:

| Sheet | Public |
| --- | --- |
| Fairview | Fairview Inn |
| Humpy's | Humpy's Great Alaskan Alehouse |
| flamingo | The Flamingo |
| Bearpaw Brewing Wasilla | Bearpaw River Brewing |
| Palmer Ale House | Palmer Alehouse |
| Forest Fair | Girdwood Forest Fair |
| chugachfest | Chugach Fest |
| Mountain High | Mountain High Pizza Pie |
| Silver Fox | The Silver Fox Inn |

Shorthand differing only in casing or a dropped article is the same venue — **keep the public
wording**. The sheet's `Notes` column maps to `note`. The sheet has no city and no ticket URL,
so those come from `shows.json` or from the user.

## Procedure

1. Read the sheet. Read `shows.json`.
2. Reconcile into three lists: **new** (in sheet, not in JSON), **changed** (date or time
   differs), **json-only** (in JSON, absent from sheet).
3. Apply date/time corrections and add new shows to `shows.json`. A new show has no city in
   the sheet — ask rather than guessing one.
4. **Do not delete a json-only show on your own.** The sheet is not reliably complete and a
   deletion erases gig history. Report it and let the user decide.
5. Run `python3 build.py`.
6. Report every discrepancy you did not auto-fix. Flag rather than silently "correct":
   - a year that looks like a typo (a past-decade date among current-season gigs)
   - a start time implausible for a gig (e.g. `4:00 AM` for a daytime festival — usually an
     AM/PM slip). Leave `time` off rather than publish it.
   - a venue whose public name is a *different name entirely* from the sheet's, rather than
     shorthand for it — a real conflict, not a formatting difference
7. Verify (below), then summarize. **Do not commit and do not deploy** unless asked.

### Known open discrepancies

Re-flag these if they still disagree; don't silently resolve them.

- **2026-02-14** — sheet says *Denali Education Center*, site says *Talkeetna Curling Club
  Bonspiel*. Unresolved conflict.
- **2026-08-26** — sheet says `8/26/2016`, a typo for 2026. Site has 2026.
- **2026-05-23** — sheet says `4:00 AM` for Talkeetna Arts Festival. Left without a time.

## Verify

```bash
cd /home/benjaminheller/dev/rbe
python3 build.py --check          # confirms index.html matches shows.json
grep -c 'class="show"' index.html # total shows, past included
```

The JSON-LD is static now, so it can be checked without a browser:

```bash
python3 - <<'PY'
import re, io, json
s = io.open('index.html', encoding='utf-8').read()
for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
    d = json.loads(b)              # also proves the JSON is valid
    if isinstance(d, list):
        for e in d:
            print(e['startDate'], '|', e['location']['name'], '|',
                  'TICKETS' if e['offers'].get('price') is None else 'free')
PY
```

Expect one line per **upcoming** show, in date order. Past shows are correctly absent — Google
only surfaces future events. This means the events region goes stale the day after each gig;
re-running `build.py` refreshes it. The deploy workflow runs `build.py --check` and fails the
deploy if it is stale, so if CI rejects a push with "index.html is out of date", the fix is to
run `python3 build.py` and commit the result.

Screenshot when layout could change (a new ticket button, a long venue name) — hide the hero
and music sections so the list is in frame, then Read the PNG:

```bash
OUT=$(mktemp -d)
sed 's|</head>|<style>.hero,.music-section{display:none!important}nav{position:static!important;opacity:1!important}</style></head>|' \
  index.html > "$OUT/preview.html"
cp -r images "$OUT/"
google-chrome --headless --disable-gpu --hide-scrollbars --window-size=1280,1200 \
  --screenshot="$OUT/shows.png" --virtual-time-budget=4000 "file://$OUT/preview.html" 2>/dev/null
```

Check mobile too (`--window-size=390,900`) if the meta column changed.

## Notes

- Timezone is Alaska; `build.py` derives AKDT/AKST from the date, so don't hardcode an offset.
- Past shows stay in `shows.json` and in the page — the runtime script hides them behind the
  "Show past shows" toggle.
