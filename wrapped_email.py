"""
"Wrapped" email for Chicago Eats & Drinks: a stats-heavy recap of a month or a whole year.

Reads the restaurants table from Supabase (only your own data; nothing from Google is
stored or emailed) and sends an HTML email with totals, firsts, favorites, breakdowns,
fun facts, your notes and photos, and a suggestion for what to try next.

Environment variables
  SUPABASE_URL, SUPABASE_ANON_KEY   same values the app uses
  SMTP_USER, SMTP_PASSWORD          sending account (Gmail: use an App Password)
  RECAP_TO                          comma-separated recipients
  SMTP_HOST / SMTP_PORT             optional, default smtp.gmail.com / 465
  WRAPPED_PERIOD                    "month" (default) or "year"
  WRAPPED_FOR                       optional: "YYYY-MM" (month) or "YYYY" (year);
                                    default = last full month / last full year
  DRY_RUN                           "true" = write wrapped_preview.html/.txt, send nothing
"""
import html
import os
import random
import smtplib
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from math import atan2, cos, radians, sin, sqrt
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

CHICAGO = ZoneInfo("America/Chicago")
LOOP = (41.8827, -87.6298)  # same center the app uses for "The Loop"
DATE_FORMAT = "%B %d, %Y"   # how the app stores visited_date, e.g. "October 22, 2026"
NOTE_LIMIT = 220
CARD_LIMIT = 12             # month mode shows full cards up to this many visits, then compact rows
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Keep in sync with NEIGHBORHOODS in app.py.
NEIGHBORHOODS = [
    "Berwyn", "Bucktown", "Chinatown", "Fulton Market", "Gold Coast", "Lincoln Park",
    "Logan Square", "Near North Side", "Oakbrook", "Oak Lawn", "Oak Park", "Old Town",
    "Pilsen", "River North", "South Loop", "The Loop", "Uptown", "West Loop", "West Town",
    "Wicker Park", "Wrigleyville",
]

WRAP = "word-break:break-word;overflow-wrap:anywhere;"
INK, LEDGER, BRASS, BRASS_BRIGHT = "#1B1712", "#2E271D", "#C9A034", "#E3C066"
WINE, CREAM, SMOKE, TEXT = "#8B2A3B", "#F1E9D8", "#A79A85", "#4A4033"


# ---------- small helpers ----------
def esc(value):
    return html.escape(str(value), quote=True)


def plural(n, word, plural_word=None):
    return f"{n} {word if n == 1 else (plural_word or word + 's')}"


def parse_visit_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except (ValueError, TypeError):
        return None


def parse_created(value):
    """created_at (ISO timestamp from Supabase) -> date in Chicago time."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(CHICAGO).date()


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def miles_between(a, b):
    r = 3958.8
    lat1, lon1, lat2, lon2 = map(radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * r * atan2(sqrt(h), sqrt(1 - h))


def top_item(counter):
    """(name, count) with the highest count; ties go alphabetically so results are stable."""
    if not counter:
        return None
    return sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))[0]


def first_note(place):
    notes = all_notes(place)
    return notes[0] if notes else None


def all_notes(place):
    out = []
    for rev in place.get("reviews") or []:
        text = rev.get("comment") if isinstance(rev, dict) else rev
        text = str(text or "").strip()
        if text:
            out.append(text)
    return out


def clip(text, limit=NOTE_LIMIT):
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def maps_link(place):
    query = f"{place.get('name', '')}, {place.get('address', '')}"
    return f"https://www.google.com/maps/search/?api=1&query={quote(query)}"


def day_label(d):
    return f"{d:%a %b} {d.day}"


def longest_week_streak(dates):
    mondays = sorted({d - timedelta(days=d.weekday()) for d in dates})
    best = run = 0
    prev = None
    for m in mondays:
        run = run + 1 if prev is not None and (m - prev).days == 7 else 1
        best = max(best, run)
        prev = m
    return best


# ---------- periods ----------
def resolve_period(kind="month", value=None, today=None):
    today = today or datetime.now(CHICAGO).date()
    if kind == "year":
        year = int(value) if value else today.year - 1
        start, end = date(year, 1, 1), date(year + 1, 1, 1)
        prev_start = date(year - 1, 1, 1)
        return {"kind": "year", "start": start, "end": end, "prev_start": prev_start,
                "prev_end": start, "label": str(year), "prev_label": str(year - 1), "year": year}
    if value:
        year, month = (int(x) for x in value.split("-"))
    else:
        year, month = today.year, today.month - 1
        if month == 0:
            year, month = year - 1, 12
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    prev_end = start
    prev_start = date(year - (month == 1), (month - 2) % 12 + 1, 1)
    return {"kind": "month", "start": start, "end": end, "prev_start": prev_start,
            "prev_end": prev_end, "label": start.strftime("%B"), "prev_label": prev_start.strftime("%B"),
            "year": year}


def in_range(d, start, end):
    return d is not None and start <= d < end


# ---------- data ----------
def fetch_places(supabase_url, supabase_key):
    resp = requests.get(
        f"{supabase_url.rstrip('/')}/rest/v1/restaurants",
        params={"select": "*"},
        headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def analyze(places, period, rng_seed=None):
    start, end = period["start"], period["end"]
    visited = [p for p in places if p.get("visited")]

    dated = [(p, parse_visit_date(p.get("visited_date"))) for p in visited]
    visits = sorted(
        ({**p, "_date": d} for p, d in dated if in_range(d, start, end)),
        key=lambda p: (p["_date"], str(p.get("name", "")).lower()),
    )
    prev_count = sum(1 for _, d in dated if in_range(d, period["prev_start"], period["prev_end"]))
    undated = sum(1 for _, d in dated if d is None)

    # Anything visited before the period, or with no date, counts as "already been there".
    prior = [p for p, d in dated if d is None or d < start]
    prior_hoods = {p.get("location") for p in prior}
    prior_cuisines = {p.get("cuisine") for p in prior}

    hoods = Counter(v.get("location") for v in visits if v.get("location"))
    cuisines = Counter(v.get("cuisine") for v in visits if v.get("cuisine"))
    prices = Counter(v.get("price") for v in visits if v.get("price"))
    types = Counter("bar" if v.get("type") == "cocktail_bar" else "restaurant" for v in visits)
    weekdays = Counter(v["_date"].weekday() for v in visits)

    price_levels = [len(v["price"]) for v in visits if v.get("price") and 1 <= len(v["price"]) <= 4]
    avg_price = sum(price_levels) / len(price_levels) if price_levels else None

    far = None
    for v in visits:
        lat, lon = to_float(v.get("latitude")), to_float(v.get("longitude"))
        if lat is None or lon is None:
            continue
        miles = miles_between(LOOP, (lat, lon))
        if far is None or miles > far[1]:
            far = (v, miles)

    unique_days = sorted({v["_date"] for v in visits})
    gap = None
    if len(unique_days) >= 2:
        gap = max(
            ((b - a).days, a, b) for a, b in zip(unique_days, unique_days[1:])
        )

    photo_total = sum(len(v.get("images") or []) for v in visits)
    most_photos = max(visits, key=lambda v: len(v.get("images") or []), default=None)
    if most_photos is not None and not (most_photos.get("images") or []):
        most_photos = None

    notes_pool = [(clip(n), v) for v in visits for n in all_notes(v)]
    quote_pick = max(notes_pool, key=lambda t: len(t[0]), default=None)

    wishlist = [p for p in places if not p.get("visited") and not p.get("retired")]
    oldest = None
    for p in wishlist:
        created = parse_created(p.get("created_at"))
        if created and (oldest is None or created < oldest[1]):
            oldest = (p, created)
    rng = random.Random(rng_seed or f"{period['kind']}-{period['label']}-{period.get('year')}")
    next_pick = rng.choice(sorted(wishlist, key=lambda p: str(p.get("name", "")))) if wishlist else None

    visited_hoods = {p.get("location") for p in visited} & set(NEIGHBORHOODS)

    month_counts = None
    if period["kind"] == "year":
        month_counts = [(date(2000, m, 1).strftime("%b"), sum(1 for v in visits if v["_date"].month == m))
                        for m in range(1, 13)]

    return {
        "period": period,
        "visits": visits,
        "count": len(visits),
        "prev_count": prev_count,
        "added": sum(1 for p in places if in_range(parse_created(p.get("created_at")), start, end)),
        "types": types,
        "hoods": hoods,
        "cuisines": cuisines,
        "prices": prices,
        "avg_price": avg_price,
        "top_hood": top_item(hoods),
        "top_cuisine": top_item(cuisines),
        "top_weekday": (sorted(weekdays.items(), key=lambda kv: (-kv[1], kv[0]))[0] if len(visits) >= 2 else None),
        "new_hoods": sorted({v.get("location") for v in visits if v.get("location")} - prior_hoods),
        "new_cuisines": sorted({v.get("cuisine") for v in visits if v.get("cuisine")} - prior_cuisines),
        "favorites": [v for v in visits if v.get("favorite")],
        "streak": longest_week_streak([v["_date"] for v in visits]),
        "gap": gap,
        "farthest": far,
        "photo_total": photo_total,
        "most_photos": most_photos,
        "notes_count": sum(1 for v in visits if all_notes(v)),
        "quote": quote_pick,
        "first_visit": visits[0] if visits else None,
        "last_visit": visits[-1] if visits else None,
        "month_counts": month_counts,
        "total_visited": len(visited),
        "undated": undated,
        "wishlist_count": len(wishlist),
        "oldest_on_list": oldest,
        "next_pick": next_pick,
        "visited_hoods": len(visited_hoods),
        "hood_total": len(NEIGHBORHOODS),
        "unexplored": [h for h in NEIGHBORHOODS if h not in visited_hoods],
    }


def delta_text(n, prev, prev_label):
    if n == 0 and prev == 0:
        return ""
    if n == prev:
        return f"same as {prev_label}"
    return f"{'up' if n > prev else 'down'} {abs(n - prev)} from {prev_label}"


# ---------- HTML pieces ----------
def _section(title, inner):
    return (
        '<tr><td style="padding:22px 22px 4px;">'
        f'<div style="font-family:Georgia,serif;font-size:20px;color:{INK};margin-bottom:10px;">{esc(title)}</div>'
        f"{inner}</td></tr>"
    )


def _tiles(items):
    rows = []
    for i in range(0, len(items), 2):
        cells = []
        for big, label, sub in items[i:i + 2]:
            sub_html = (f'<div style="font-size:12px;color:{SMOKE};margin-top:3px;">{esc(sub)}</div>' if sub else "")
            cells.append(
                f'<td width="50%" valign="top" style="background:{LEDGER};border:5px solid #FBF6EA;border-radius:12px;padding:16px 14px;">'
                f'<div style="font-family:Georgia,serif;font-size:32px;line-height:1.1;color:{BRASS_BRIGHT};">{esc(big)}</div>'
                f'<div style="font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:{CREAM};margin-top:6px;">{esc(label)}</div>'
                f"{sub_html}</td>"
            )
        if len(cells) == 1:
            cells.append('<td width="50%"></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + "".join(rows) + "</table>"


def _facts(rows):
    out = []
    for label, value in rows:
        out.append(
            "<tr>"
            f'<td valign="top" width="38%" style="padding:6px 10px 6px 0;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:{SMOKE};">{esc(label)}</td>'
            f'<td valign="top" style="padding:6px 0;font-size:15px;color:{INK};{WRAP}">{value}</td>'
            "</tr>"
        )
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + "".join(out) + "</table>"


def _bars(items, color=BRASS):
    if not items:
        return ""
    top = max(n for _, n in items) or 1
    rows = []
    for label, n in items:
        pct = 0 if n == 0 else max(4, round(100 * n / top))
        rows.append(
            "<tr>"
            f'<td width="36%" style="padding:3px 10px 3px 0;font-size:13px;color:{TEXT};">{esc(label)}</td>'
            '<td style="padding:3px 0;"><div style="background:#E8DEC6;border-radius:4px;">'
            f'<div style="width:{pct}%;background:{color};height:10px;border-radius:4px;"></div></div></td>'
            f'<td width="30" align="right" style="padding:3px 0 3px 8px;font-size:13px;color:{TEXT};">{n}</td>'
            "</tr>"
        )
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + "".join(rows) + "</table>"


def _card(p):
    meta = " · ".join(esc(x) for x in [p.get("cuisine"), p.get("price"), p.get("location")] if x)
    fav = f' <span style="color:{WINE};">♥</span>' if p.get("favorite") else ""
    images = p.get("images") or []
    photo = (
        f'<img src="{esc(images[0])}" alt="" width="100%" style="display:block;width:100%;max-height:220px;'
        'object-fit:cover;border-radius:6px;margin:10px 0 4px;">'
        if images else ""
    )
    note = first_note(p)
    note_html = (f'<div style="margin-top:8px;color:{TEXT};font-style:italic;{WRAP}">“{esc(clip(note))}”</div>' if note else "")
    return (
        f'<div style="background:#FFFDF7;border:1px solid #E3D8BE;border-left:4px solid {BRASS};'
        'border-radius:6px;padding:14px 16px;margin:0 0 10px;">'
        f'<div style="font-size:12px;color:{SMOKE};letter-spacing:.06em;text-transform:uppercase;">{day_label(p["_date"])}</div>'
        f'<div style="font-family:Georgia,serif;font-size:19px;color:{INK};margin:2px 0;{WRAP}">{esc(p.get("name", ""))}{fav}</div>'
        f'<div style="font-size:13px;color:#6B5E48;">{meta}</div>{photo}{note_html}'
        f'<div style="margin-top:10px;"><a href="{esc(maps_link(p))}" style="color:#8B6B12;font-size:13px;">Open in Google Maps</a></div>'
        "</div>"
    )


def _compact_rows(visits):
    rows = []
    for p in visits:
        fav = f' <span style="color:{WINE};">♥</span>' if p.get("favorite") else ""
        rows.append(
            "<tr>"
            f'<td width="72" valign="top" style="padding:4px 10px 4px 0;font-size:12px;color:{SMOKE};">{day_label(p["_date"])}</td>'
            f'<td style="padding:4px 0;font-size:14px;color:{INK};{WRAP}"><a href="{esc(maps_link(p))}" style="color:{INK};text-decoration:none;">{esc(p.get("name", ""))}</a>{fav}'
            f'<span style="color:{SMOKE};font-size:12px;"> · {esc(p.get("location") or "")}</span></td>'
            "</tr>"
        )
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + "".join(rows) + "</table>"


def _name_list(places):
    return ", ".join(esc(p.get("name", "")) for p in places)


# ---------- the email ----------
def build_email(s):
    period = s["period"]
    label = period["label"]
    n = s["count"]
    is_year = period["kind"] == "year"
    span = f"{label}" if is_year else f"{label} {period['year']}"
    subject = f"Your {label}, Wrapped: {plural(n, 'place')}" if n else f"Your {label}, Wrapped: a quiet one"

    # ----- tiles -----
    tiles = [(str(n), "places visited", delta_text(n, s["prev_count"], period["prev_label"])),
             (str(s["added"]), "added to the list", "")]
    r, b = s["types"].get("restaurant", 0), s["types"].get("bar", 0)
    if n:
        tiles.append((f"{r} / {b}", "restaurants / bars", ""))
        if s["avg_price"]:
            tiles.append(("$" * max(1, round(s["avg_price"])), "typical price", f"average {s['avg_price']:.1f} of 4"))

    # ----- fact rows -----
    facts = []
    if s["top_cuisine"]:
        facts.append(("Top cuisine", f"<b>{esc(s['top_cuisine'][0])}</b> ({s['top_cuisine'][1]} of {n})"))
    if s["top_hood"]:
        facts.append(("Top neighborhood", f"<b>{esc(s['top_hood'][0])}</b> ({s['top_hood'][1]} of {n})"))
    if s["top_weekday"]:
        facts.append(("Favorite night out", f"<b>{WEEKDAYS[s['top_weekday'][0]]}s</b> ({s['top_weekday'][1]} of {n})"))
    if is_year and s["month_counts"] and n:
        best = sorted(s["month_counts"], key=lambda t: -t[1])[0]
        facts.append(("Busiest month", f"<b>{esc(best[0])}</b> ({plural(best[1], 'place')})"))
    if s["first_visit"] and is_year:
        facts.append(("First of the year", f"{esc(s['first_visit']['name'])} · {day_label(s['first_visit']['_date'])}"))
        if s["last_visit"] is not s["first_visit"]:
            facts.append(("Latest", f"{esc(s['last_visit']['name'])} · {day_label(s['last_visit']['_date'])}"))
    if s["new_hoods"]:
        facts.append(("New neighborhoods", f"<b>{esc(', '.join(s['new_hoods']))}</b>"))
    if s["new_cuisines"]:
        facts.append(("New cuisines", f"<b>{esc(', '.join(s['new_cuisines']))}</b>"))
    if s["favorites"]:
        facts.append(("Favorites visited", _name_list(s["favorites"])))
    if s["farthest"]:
        v, miles = s["farthest"]
        if miles >= 3:
            facts.append(("Farthest trip", f"{esc(v['name'])}, <b>{miles:.0f} mi</b> from the Loop"))
    if s["streak"] >= 2:
        facts.append(("Longest streak", f"<b>{s['streak']} weeks</b> in a row with a night out"))
    if s["gap"] and s["gap"][0] >= 7:
        days, a, c = s["gap"]
        facts.append(("Longest break", f"{days} days ({day_label(a)} to {day_label(c)})"))
    if s["photo_total"]:
        extra = (f" · most from {esc(s['most_photos']['name'])}" if s["most_photos"] else "")
        facts.append(("Photos", f"{plural(s['photo_total'], 'photo')}{extra}"))
    if s["notes_count"]:
        facts.append(("Notes written", f"{s['notes_count']} of {n}"))

    # ----- sections -----
    sections = []
    sections.append(_section("The numbers", _tiles(tiles)))
    if facts:
        sections.append(_section("Highlights", _facts(facts)))
    if s["quote"]:
        text, v = s["quote"]
        sections.append(_section(
            "From your notes",
            f'<div style="font-style:italic;color:{TEXT};font-size:15px;{WRAP}">“{esc(text)}”</div>'
            f'<div style="font-size:12px;color:{SMOKE};margin-top:4px;">{esc(v["name"])}</div>',
        ))
    if is_year and s["month_counts"] and n:
        sections.append(_section("Month by month", _bars(s["month_counts"])))
    breakdown = ""
    if s["hoods"]:
        breakdown += f'<div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:{SMOKE};margin:4px 0;">Neighborhoods</div>'
        breakdown += _bars(s["hoods"].most_common(6))
    if s["cuisines"]:
        breakdown += f'<div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:{SMOKE};margin:14px 0 4px;">Cuisines</div>'
        breakdown += _bars(s["cuisines"].most_common(6), WINE)
    if s["prices"]:
        price_items = [(p, s["prices"][p]) for p in ["$", "$$", "$$$", "$$$$"] if s["prices"].get(p)]
        breakdown += f'<div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:{SMOKE};margin:14px 0 4px;">Price</div>'
        breakdown += _bars(price_items, "#6B8863")
    if breakdown:
        sections.append(_section("Breakdown", breakdown))
    if s["visits"]:
        show_cards = (not is_year) and n <= CARD_LIMIT
        title = "Every stop" if is_year or not show_cards else "Where you went"
        body = "".join(_card(v) for v in s["visits"]) if show_cards else _compact_rows(s["visits"])
        sections.append(_section(title, body))
    else:
        sections.append(_section("Where you went",
                                 f'<div style="color:{TEXT};">Nothing was marked visited with a date in {esc(span)}.</div>'))

    # ----- progress + next up -----
    pct = round(100 * s["visited_hoods"] / s["hood_total"]) if s["hood_total"] else 0
    progress = (
        f'<div style="font-size:15px;color:{INK};"><b>{s["visited_hoods"]} of {s["hood_total"]}</b> neighborhoods explored</div>'
        '<div style="background:#E8DEC6;border-radius:4px;margin:8px 0;">'
        f'<div style="width:{max(2, pct)}%;background:{BRASS};height:10px;border-radius:4px;"></div></div>'
    )
    if s["unexplored"]:
        shown = s["unexplored"][:6]
        more = f" and {len(s['unexplored']) - 6} more" if len(s["unexplored"]) > 6 else ""
        progress += f'<div style="font-size:13px;color:{TEXT};">Still to try: {esc(", ".join(shown))}{more}</div>'
    progress += (
        f'<div style="font-size:13px;color:{TEXT};margin-top:8px;">{s["total_visited"]} places visited all time · '
        f'{s["wishlist_count"]} still on the list</div>'
    )
    if s["oldest_on_list"]:
        p, created = s["oldest_on_list"]
        progress += (f'<div style="font-size:13px;color:{TEXT};margin-top:4px;">On the list longest: '
                     f'<b>{esc(p["name"])}</b> (since {created:%b %Y})</div>')
    sections.append(_section("Your map so far", progress))

    if s["next_pick"]:
        p = s["next_pick"]
        meta = " · ".join(esc(x) for x in [p.get("cuisine"), p.get("price"), p.get("location")] if x)
        sections.append(_section(
            "Next up?",
            f'<div style="background:#FFFDF7;border:1px dashed {BRASS};border-radius:6px;padding:14px 16px;">'
            f'<div style="font-family:Georgia,serif;font-size:19px;color:{INK};">{esc(p.get("name", ""))}</div>'
            f'<div style="font-size:13px;color:#6B5E48;margin-top:2px;">{meta}</div>'
            f'<div style="margin-top:8px;"><a href="{esc(maps_link(p))}" style="color:#8B6B12;font-size:13px;">Open in Google Maps</a></div></div>',
        ))

    footer = ""
    if s["undated"]:
        footer = (f"{plural(s['undated'], 'visited place')} ha{'s' if s['undated'] == 1 else 've'} no visit date, "
                  "so they aren't counted in a month or year. Add dates in the app to include them.")

    big = (
        f'<div style="font-family:Georgia,serif;font-size:64px;line-height:1;color:{BRASS_BRIGHT};margin-top:14px;">{n}</div>'
        f'<div style="font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:{SMOKE};margin-top:6px;">'
        f'{"place" if n == 1 else "places"} in {esc(span)}</div>'
    )
    body = (
        f'<div style="background:{CREAM};padding:24px 12px;font-family:Helvetica,Arial,sans-serif;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">'
        f'<tr><td style="background:{INK};border-radius:10px 10px 0 0;padding:30px 20px 26px;text-align:center;">'
        f'<div style="font-size:11px;letter-spacing:.28em;text-transform:uppercase;color:{BRASS};">Chicago Eats &amp; Drinks</div>'
        f'<div style="font-family:Georgia,serif;font-size:32px;color:{BRASS_BRIGHT};margin-top:8px;">Your {esc(label)}, Wrapped</div>'
        f"{big}</td></tr>"
        f'<tr><td style="background:#FBF6EA;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        + "".join(sections)
        + "</table></td></tr>"
        f'<tr><td style="background:#FBF6EA;border-radius:0 0 10px 10px;padding:18px 22px 24px;font-size:12px;color:{SMOKE};text-align:center;">'
        f"{esc(footer)}</td></tr></table></div>"
    )
    return subject, body, build_text(s, span)


def build_text(s, span):
    period = s["period"]
    n = s["count"]
    lines = [f"Chicago Eats & Drinks - Your {period['label']}, Wrapped", "",
             f"{plural(n, 'place')} in {span}"]
    d = delta_text(n, s["prev_count"], period["prev_label"])
    if d:
        lines[-1] += f" ({d})"
    lines.append(f"{s['added']} added to the list")
    if n:
        lines.append(f"{plural(s['types'].get('restaurant', 0), 'restaurant')}, {plural(s['types'].get('bar', 0), 'bar')}")
        if s["avg_price"]:
            lines.append(f"Typical price: {'$' * max(1, round(s['avg_price']))} (avg {s['avg_price']:.1f}/4)")
    lines.append("")
    if s["top_cuisine"]:
        lines.append(f"Top cuisine: {s['top_cuisine'][0]} ({s['top_cuisine'][1]} of {n})")
    if s["top_hood"]:
        lines.append(f"Top neighborhood: {s['top_hood'][0]} ({s['top_hood'][1]} of {n})")
    if s["top_weekday"]:
        lines.append(f"Favorite night out: {WEEKDAYS[s['top_weekday'][0]]}s")
    if s["new_hoods"]:
        lines.append(f"New neighborhoods: {', '.join(s['new_hoods'])}")
    if s["new_cuisines"]:
        lines.append(f"New cuisines: {', '.join(s['new_cuisines'])}")
    if s["favorites"]:
        lines.append("Favorites visited: " + ", ".join(p.get("name", "") for p in s["favorites"]))
    if s["farthest"] and s["farthest"][1] >= 3:
        lines.append(f"Farthest trip: {s['farthest'][0]['name']} ({s['farthest'][1]:.0f} mi from the Loop)")
    if s["streak"] >= 2:
        lines.append(f"Longest streak: {s['streak']} weeks in a row")
    if s["photo_total"]:
        lines.append(f"Photos: {s['photo_total']}")
    if s["quote"]:
        lines += ["", f"\"{s['quote'][0]}\" - {s['quote'][1]['name']}"]
    lines += ["", "Where you went:"]
    for p in s["visits"]:
        fav = " <3" if p.get("favorite") else ""
        lines.append(f"  {day_label(p['_date'])}  {p.get('name', '')}{fav} ({p.get('location') or ''})")
    if not s["visits"]:
        lines.append("  Nothing marked visited with a date in that period.")
    lines += ["", f"{s['visited_hoods']} of {s['hood_total']} neighborhoods explored",
              f"{s['total_visited']} visited all time, {s['wishlist_count']} still on the list"]
    if s["next_pick"]:
        lines.append(f"Next up? {s['next_pick'].get('name', '')} - {maps_link(s['next_pick'])}")
    if s["undated"]:
        lines.append(f"({plural(s['undated'], 'visited place')} without a date not counted.)")
    return "\n".join(lines)


# ---------- sending ----------
def send_email(subject, html_body, text_body):
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    recipients = [a.strip() for a in os.environ["RECAP_TO"].split(",") if a.strip()]
    if not recipients:
        raise SystemExit("RECAP_TO has no recipients.")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=30) as server:
        server.login(user, password)
        server.send_message(msg)
    return recipients


def main():
    kind = (os.environ.get("WRAPPED_PERIOD") or "month").strip().lower()
    if kind not in ("month", "year"):
        raise SystemExit(f"WRAPPED_PERIOD must be 'month' or 'year', not {kind!r}")
    period = resolve_period(kind, os.environ.get("WRAPPED_FOR") or None)
    places = fetch_places(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    subject, html_body, text_body = build_email(analyze(places, period))

    if os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes"):
        with open("wrapped_preview.html", "w", encoding="utf-8") as f:
            f.write(html_body)
        with open("wrapped_preview.txt", "w", encoding="utf-8") as f:
            f.write(text_body)
        print(f"DRY RUN - not sent.\nSubject: {subject}\n\n{text_body}")
        return
    recipients = send_email(subject, html_body, text_body)
    print(f"Sent '{subject}' to {len(recipients)} recipient(s).")


if __name__ == "__main__":
    sys.exit(main())
