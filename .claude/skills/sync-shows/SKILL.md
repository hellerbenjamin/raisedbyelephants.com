---
name: sync-shows
description: Sync the Shows section of index.html from the band's gig Google Sheet — add new gigs, correct dates and set times, and refresh the MusicEvent structured data. Use when asked to update shows, add a gig, fix show dates/times, or reconcile the site with the sheet.
---

# Sync shows from the gig sheet

The gig sheet is the source of truth for **which shows exist, on what date, at what time**.
`index.html` is the source of truth for **how a show is presented** — public venue name, city,
and ticket link. Sync in that direction; never let one overwrite the other's half.

Sheet: https://docs.google.com/spreadsheets/d/1H4mRoEbsmvMWRXivfjBhjwHnb0WsAYqtu2nsf1ubVwM/edit
File ID: `1H4mRoEbsmvMWRXivfjBhjwHnb0WsAYqtu2nsf1ubVwM`

## Read the sheet

Use `mcp__claude_ai_Google_Drive__read_file_content` with the file ID above.

Columns: `Date | Start Time | Length | Notes | Venue | <one column per member>`

**The member columns are availability tracking, not public data.** They are names with
TRUE/FALSE. Never publish them, never infer a lineup change from them, never mention who
was marked unavailable. Read only Date, Start Time, Length, Notes, Venue.

## Markup contract

Each gig in the `.shows-list` of `index.html` looks like this:

```html
<div class="show" data-date="2026-09-25" data-tickets="https://...">
    <div class="show-date">
        SEP<br>25
    </div>
    <div class="show-details">
        <h4>Odd Man Rush Brewing &bull; EP Release</h4>
        <p>Eagle River, AK</p>
    </div>
    <div class="show-meta">
        <a href="https://..." target="_blank" rel="noopener"
           class="btn ticket-btn">Tickets</a>
    </div>
</div>
```

- `data-date` (`YYYY-MM-DD`) is what the page's JS reads to split past from upcoming and to
  build the JSON-LD. The `SEP<br>25` text is display only — **keep the two in agreement**.
- `data-time` (`HH:MM`, 24-hour) is optional. When present the JSON-LD emits a full
  `startDate` timestamp with Alaska's offset instead of a bare date, which Google prefers.
- `data-tickets` is optional; a show that has it renders a **Tickets** button, one that
  doesn't renders a muted **Free** badge.
- Shows are listed **chronologically, oldest first**. The `More coming soon...` div stays last.
- Past shows are hidden automatically at runtime — do not delete them.

## Matching sheet rows to page shows

Match on `data-date` first, then venue. Venue strings in the sheet are internal shorthand and
often differ from the public name on the page. Known pairs:

| Sheet | Page |
| --- | --- |
| Fairview | Fairview Inn |
| Humpy's | Humpy's Great Alaskan Alehouse |
| flamingo | The Flamingo |
| Bearpaw Brewing Wasilla | Bearpaw River Brewing |
| Palmer Ale House | Palmer Alehouse |
| Forest Fair | Girdwood Forest Fair |
| chugachfest | Chugach Fest |
| Mountain High | Mountain High Pizza Pie |

A shorthand that differs only in casing or a dropped article is the same venue. **Keep the
page's wording** — it is the public-facing one.

The sheet's `Notes` column maps to the ` &bull; ` qualifier on the page
(`Odd Man Rush Brewing &bull; EP Release`). The sheet has no city and no ticket URL, so those
can only come from the page or from the user.

## Procedure

1. Read the sheet. Read the current `.show` blocks out of `index.html`.
2. Reconcile, and build three lists: **new** (in sheet, not on page), **changed** (date or
   time differs), **page-only** (on page, absent from sheet).
3. Apply date and time corrections, and add new shows in chronological position. For a new
   show you will not have a city or ticket link — ask rather than guessing a city.
4. **Do not delete a page-only show on your own.** The sheet is not reliably complete, and a
   deletion erases history. Report it and let the user decide.
5. Report every discrepancy you did not auto-fix. Flag rather than silently "correct":
   - a year that looks like a typo (a past-decade date among current-season gigs)
   - a start time that is implausible for a gig (e.g. `4:00 AM` for a daytime festival, which
     is usually a spreadsheet AM/PM slip)
   - a venue on the page that is a different name entirely from the sheet's, rather than
     shorthand for it — that is a real conflict, not a formatting difference
6. Verify (see below), then summarize. **Do not commit and do not deploy** unless asked.

## Verify

Render the page and confirm the generated structured data matches the sheet:

```bash
cd /home/benjaminheller/dev/rbe
OUT=$(mktemp -d)
google-chrome --headless --disable-gpu --dump-dom --virtual-time-budget=4000 \
  "file://$PWD/index.html" 2>/dev/null > "$OUT/dom.html"
python3 - "$OUT/dom.html" <<'PY'
import re, sys, json, io
s = io.open(sys.argv[1], encoding='utf-8').read()
blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
for b in blocks:
    d = json.loads(b)            # also proves the JSON is valid
    if isinstance(d, list):
        for e in d:
            print(e['startDate'], '|', e['location']['name'], '|',
                  'TICKETS' if 'eventbrite' in e['offers']['url'] else 'free')
PY
```

Expect one line per **upcoming** show, in date order. Past shows are correctly absent — Google
only surfaces future events. Also check the count of `.show` divs matches what you expect:

```bash
grep -c 'class="show"' index.html
```

A screenshot is worth it when layout changed (a new ticket button, a long venue name). Hide the
hero and music sections so the shows list is in frame:

```bash
sed 's|</head>|<style>.hero,.music-section{display:none!important}nav{position:static!important;opacity:1!important}</style></head>' \
  index.html > "$OUT/preview.html"
cp -r images "$OUT/"
google-chrome --headless --disable-gpu --hide-scrollbars --window-size=1280,1500 \
  --screenshot="$OUT/shows.png" --virtual-time-budget=4000 "file://$OUT/preview.html" 2>/dev/null
```

Then Read the PNG. Check mobile too (`--window-size=390,900`) if you touched the meta column.

## Notes

- Timezone is Alaska: `-08:00` AKDT roughly Mar–Nov, `-09:00` AKST otherwise.
- The section heading is hardcoded `2026 Shows`; update it when the season rolls over.
- The JSON-LD is generated at runtime from this markup, so there is no second place to edit —
  fixing `data-date`/`data-time` fixes the structured data too.
