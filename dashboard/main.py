"""
Pi Calendar - main entry point.

Run on a schedule (see systemd/dashboard-render.timer). Each run:
  1. Loads config.yaml
  2. Fetches each calendar feed (ICS) and the Microsoft To Do list
  3. Renders a single PNG (dark theme: this-week row + month grid + to-do sidebar)
  4. Saves it to dashboard/current.png for the display service to show

See docs/PLAN.md for the full architecture and rollout plan.

First run note: the very first time this runs, fetch_todo() will print a
message like "To sign in, use a web browser to open https://microsoft.com/devicelogin
and enter the code XXXXXXXX to authenticate." Go to that URL on any device,
enter the code, and sign in with the same personal Microsoft account you
registered the Azure app with. After that one-time step, a token is cached
in token_cache.json next to this script and future runs are silent.
"""
import calendar
import datetime
import json
import os
import sys

import yaml
from PIL import Image, ImageDraw, ImageFont

try:
    import msal
except ImportError:
    msal = None

try:
    import requests
except ImportError:
    requests = None

try:
    import icalendar
    import recurring_ical_events
except ImportError:
    icalendar = None
    recurring_ical_events = None


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(SCRIPT_DIR, "fonts")
CONFIG_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "config.yaml")
TOKEN_CACHE_PATH = os.path.join(SCRIPT_DIR, "token_cache.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "current.png")

GRAPH_SCOPES = ["Tasks.ReadWrite"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Fallback colors (by calendar "name" in config.yaml) used only if a
# calendar entry doesn't specify its own "color".
DEFAULT_COLORS = [
    "#4285F4",  # blue
    "#AB47BC",  # purple
    "#FFA726",  # orange
    "#26C6AA",  # teal
]


def log(msg):
    print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 1. Config
# ---------------------------------------------------------------------------

def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"config.yaml not found at {path}. Copy config.example.yaml to "
            f"config.yaml (next to it, one level up from dashboard/) and fill "
            f"in your real values first."
        )
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    config.setdefault("display", {})
    config["display"].setdefault("width", 1366)
    config["display"].setdefault("height", 768)
    config["display"].setdefault("refresh_minutes", 5)
    config.setdefault("calendars", [])
    config.setdefault("microsoft_todo", {})
    return config


# ---------------------------------------------------------------------------
# 2. Calendars (ICS feeds)
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def fetch_calendars(config, window_start, window_end):
    """
    Returns (events_by_date, source_colors):
      events_by_date: {date: [(time_str, title, source_name), ...], ...}
      source_colors:  {source_name: (r, g, b), ...}
    A calendar that fails to fetch/parse is skipped with a logged warning
    rather than crashing the whole render - a stale picture for one
    calendar is better than no dashboard at all.
    """
    events_by_date = {}
    source_colors = {}

    calendars = config.get("calendars") or []
    for i, cal_cfg in enumerate(calendars):
        name = cal_cfg.get("name", f"calendar{i}")
        url = cal_cfg.get("url")
        color = cal_cfg.get("color") or DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
        source_colors[name] = hex_to_rgb(color)

        if not url or "example.com" in url:
            log(f"skipping calendar '{name}': no real URL configured yet")
            continue
        if icalendar is None or recurring_ical_events is None:
            log("icalendar / recurring_ical_events not installed - skipping calendar fetch")
            continue

        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            cal = icalendar.Calendar.from_ical(resp.content)
            occurrences = recurring_ical_events.of(cal).between(window_start, window_end)
        except Exception as e:
            log(f"failed to fetch/parse calendar '{name}': {e}")
            continue

        for ev in occurrences:
            dtstart = ev.get("dtstart").dt
            if isinstance(dtstart, datetime.datetime):
                ev_date = dtstart.date()
                time_str = dtstart.strftime("%H:%M")
            else:
                # all-day event
                ev_date = dtstart
                time_str = "All day"
            title = str(ev.get("summary", "(no title)"))
            events_by_date.setdefault(ev_date, []).append((time_str, title, name))

    # sort each day's events by time
    for day in events_by_date:
        events_by_date[day].sort(key=lambda e: e[0])

    return events_by_date, source_colors


# ---------------------------------------------------------------------------
# 3. Microsoft To Do (Graph API, device code flow)
# ---------------------------------------------------------------------------

def _load_token_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_PATH):
        with open(TOKEN_CACHE_PATH, "r") as f:
            cache.deserialize(f.read())
    return cache


def _save_token_cache(cache):
    if cache.has_state_changed:
        with open(TOKEN_CACHE_PATH, "w") as f:
            f.write(cache.serialize())


def _get_graph_token(config):
    client_id = config.get("microsoft_todo", {}).get("client_id")
    if not client_id or "YOUR_AZURE_APP_CLIENT_ID" in client_id:
        log("microsoft_todo.client_id not configured yet - skipping To Do fetch")
        return None

    cache = _load_token_cache()
    app = msal.PublicClientApplication(
        client_id,
        authority="https://login.microsoftonline.com/consumers",
        token_cache=cache,
    )

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
        if "user_code" not in flow:
            log(f"failed to start device login flow: {flow}")
            return None
        # This is the one-time, human-readable sign-in prompt - it needs to
        # reach wherever you're watching stdout/stderr for this script.
        print(flow["message"], file=sys.stderr)
        result = app.acquire_token_by_device_flow(flow)

    _save_token_cache(cache)

    if "access_token" not in result:
        log(f"failed to acquire Graph token: {result.get('error_description', result)}")
        return None
    return result["access_token"]


def fetch_todo(config):
    """Returns [(title, done_bool), ...] from the user's Microsoft To Do list."""
    if msal is None or requests is None:
        log("msal / requests not installed - skipping To Do fetch")
        return []

    token = _get_graph_token(config)
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    list_name = config.get("microsoft_todo", {}).get("list_name") or ""

    try:
        lists_resp = requests.get(f"{GRAPH_BASE}/me/todo/lists", headers=headers, timeout=20)
        lists_resp.raise_for_status()
        lists = lists_resp.json().get("value", [])
    except Exception as e:
        log(f"failed to fetch To Do lists: {e}")
        return []

    target_list = None
    if list_name:
        target_list = next((l for l in lists if l.get("displayName") == list_name), None)
    if target_list is None and lists:
        # fall back to the default "Tasks" list (usually first returned)
        target_list = lists[0]
    if target_list is None:
        log("no Microsoft To Do lists found")
        return []

    list_id = target_list["id"]
    try:
        tasks_resp = requests.get(
            f"{GRAPH_BASE}/me/todo/lists/{list_id}/tasks"
            f"?$filter=status ne 'completed'&$top=50",
            headers=headers, timeout=20,
        )
        tasks_resp.raise_for_status()
        open_tasks = tasks_resp.json().get("value", [])

        done_resp = requests.get(
            f"{GRAPH_BASE}/me/todo/lists/{list_id}/tasks"
            f"?$filter=status eq 'completed'&$top=10",
            headers=headers, timeout=20,
        )
        done_resp.raise_for_status()
        done_tasks = done_resp.json().get("value", [])
    except Exception as e:
        log(f"failed to fetch To Do tasks: {e}")
        return []

    todos = [(t.get("title", "(untitled)"), False) for t in open_tasks]
    todos += [(t.get("title", "(untitled)"), True) for t in done_tasks]
    return todos


# ---------------------------------------------------------------------------
# 4. Render (adapted from the approved dark-theme mockup)
# ---------------------------------------------------------------------------

def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS_DIR, name), size)


def _wrap_text(draw, text, f, max_w):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _truncate(draw, text, f, max_w):
    if draw.textlength(text, font=f) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…"


def _day_label(d, today):
    diff = (d - today).days
    if diff == 0:
        return "TODAY"
    if diff == 1:
        return "TOMORROW"
    return d.strftime("%a").upper()


def render(events_by_date, source_colors, todos, config):
    width = config["display"]["width"]
    height = config["display"]["height"]
    today = datetime.date.today()
    now_time = datetime.datetime.now().strftime("%H:%M")

    # Dark theme palette (the finalized design) - the only theme this build
    # ships with; see docs/PLAN.md if a light variant is ever wanted later.
    bg = (16, 18, 23)
    panel_bg = (24, 27, 34)
    off_month_bg = (19, 21, 27)
    fg = (232, 234, 238)
    dim = (150, 155, 166)
    faint = (85, 90, 100)
    border = (42, 46, 55)
    today_blue = (100, 165, 255)
    checkbox_done_bg = (30, 50, 40)

    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)

    f_time = _font("WorkSans-Bold.ttf", 30)
    f_wk_day = _font("WorkSans-Bold.ttf", 15)
    f_wk_date = _font("WorkSans-Regular.ttf", 12)
    f_wk_ev = _font("WorkSans-Regular.ttf", 13)
    f_wk_free = _font("WorkSans-Regular.ttf", 12)
    f_mo_title = _font("WorkSans-Bold.ttf", 20)
    f_wd = _font("WorkSans-Bold.ttf", 12)
    f_daynum = _font("WorkSans-Bold.ttf", 14)
    f_daynum_dim = _font("WorkSans-Regular.ttf", 14)
    f_h2 = _font("WorkSans-Bold.ttf", 20)
    f_todo = _font("WorkSans-Regular.ttf", 18)
    f_date_small = _font("WorkSans-Regular.ttf", 14)
    f_title = _font("WorkSans-Bold.ttf", 26)

    pad = 28
    d.text((width - pad - 95, 10), now_time, font=f_time, fill=fg, anchor="la")
    d.text((width - pad - 145, 44), today.strftime("%A, %b %d"), font=f_date_small, fill=dim)
    d.text((pad, 20), "This week", font=f_title, fill=fg)

    sidebar_w = max(180, int(width * 0.16))
    gap = 20
    content_x0 = pad
    content_x1 = width - pad - sidebar_w - gap

    # ----- Week band -----
    week_y0 = 62
    week_h = int(height * 0.38)
    col_w = (content_x1 - content_x0) / 7

    for i in range(7):
        day = today + datetime.timedelta(days=i)
        x0 = content_x0 + i * col_w
        x1 = x0 + col_w
        is_today = (i == 0)
        d.rectangle([x0, week_y0, x1, week_y0 + week_h], fill=panel_bg, outline=border, width=1)
        if is_today:
            d.rectangle([x0 + 2, week_y0 + 2, x1 - 2, week_y0 + week_h - 2], outline=today_blue, width=3)

        inner = 10
        d.text((x0 + inner, week_y0 + 10), _day_label(day, today),
                font=f_wk_day, fill=(today_blue if is_today else fg))
        d.text((x0 + inner, week_y0 + 30), day.strftime("%b %d"), font=f_wk_date, fill=dim)

        ey = week_y0 + 54
        evs = events_by_date.get(day, [])
        max_ey = week_y0 + week_h - 14
        if not evs:
            d.text((x0 + inner, ey), "No meetings", font=f_wk_free, fill=faint)
        else:
            for idx, (time_str, title, source) in enumerate(evs):
                if ey > max_ey - 14:
                    d.text((x0 + inner, ey), f"+{len(evs) - idx} more", font=f_wk_free, fill=dim)
                    break
                color = source_colors.get(source, (150, 150, 150))
                d.rectangle([x0 + inner, ey + 2, x0 + inner + 4, ey + 12], fill=color)
                lines = _wrap_text(d, f"{time_str} {title}", f_wk_ev, col_w - inner * 2 - 8)
                for line in lines[:2]:
                    d.text((x0 + inner + 9, ey), line, font=f_wk_ev, fill=fg)
                    ey += 16
                ey += 6

    # ----- Month grid (compact, dots only) -----
    month_y0 = week_y0 + week_h + 18
    month_y1 = height - pad
    d.text((content_x0, month_y0), today.strftime("%B %Y"), font=f_mo_title, fill=fg)
    grid_y0 = month_y0 + 32
    weekday_h = 22

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(today.year, today.month)
    n_rows = len(weeks)
    cell_w = (content_x1 - content_x0) / 7
    cell_h = (month_y1 - grid_y0 - weekday_h) / n_rows

    for i, wd in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        cx = content_x0 + i * cell_w + cell_w / 2
        d.text((cx, grid_y0 + weekday_h / 2), wd, font=f_wd, fill=dim, anchor="mm")

    grid_top = grid_y0 + weekday_h
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week):
            x0 = content_x0 + di * cell_w
            y0 = grid_top + wi * cell_h
            x1 = x0 + cell_w
            y1 = y0 + cell_h
            in_month = day.month == today.month
            is_today = day == today
            d.rectangle([x0, y0, x1, y1], fill=panel_bg if in_month else off_month_bg, outline=border, width=1)
            if is_today:
                d.rectangle([x0 + 2, y0 + 2, x1 - 2, y1 - 2], outline=today_blue, width=2)
            num_font = f_daynum if in_month else f_daynum_dim
            num_col = today_blue if is_today else (fg if in_month else faint)
            d.text((x0 + 8, y0 + 4), str(day.day), font=num_font, fill=num_col)
            if in_month:
                evs = events_by_date.get(day, [])
                sources = list({s for _, _, s in evs})[:4]
                dx = x0 + cell_w - 12
                for s in sources:
                    d.ellipse([dx - 5, y0 + 8, dx + 5, y0 + 18], fill=source_colors.get(s, (150, 150, 150)))
                    dx -= 12

    # ----- Sidebar: to-do -----
    side_x = content_x1 + gap
    d.rounded_rectangle([side_x, week_y0, width - pad, month_y1], radius=16, fill=panel_bg, outline=border, width=1)
    inner = 20
    d.text((side_x + inner, week_y0 + inner), "To-do", font=f_h2, fill=fg)
    y = week_y0 + inner + 44
    max_y = month_y1 - inner
    if not todos:
        d.text((side_x + inner, y), "No tasks", font=f_todo, fill=faint)
    for title, done in todos:
        if y + 24 > max_y:
            break
        box_col = (90, 180, 120) if done else dim
        d.rounded_rectangle([side_x + inner, y + 2, side_x + inner + 22, y + 24], radius=5,
                             outline=box_col, width=3, fill=checkbox_done_bg if done else None)
        if done:
            d.line([(side_x + inner + 4, y + 13), (side_x + inner + 9, y + 18), (side_x + inner + 18, y + 6)],
                   fill=(60, 150, 90), width=3)
        text_fill = dim if done else fg
        text = _truncate(d, title, f_todo, sidebar_w - inner * 2 - 32)
        d.text((side_x + inner + 32, y), text, font=f_todo, fill=text_fill)
        y += 42

    return img


# ---------------------------------------------------------------------------
# 5. main
# ---------------------------------------------------------------------------

def main():
    config = load_config()

    today = datetime.date.today()
    # Window wide enough to cover both the 7-day week band and the full
    # month grid (which can show a few days of the adjacent month too).
    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdatescalendar(today.year, today.month)
    window_start = min(month_weeks[0][0], today)
    window_end = max(month_weeks[-1][-1], today + datetime.timedelta(days=7))

    events_by_date, source_colors = fetch_calendars(config, window_start, window_end)
    todos = fetch_todo(config)

    img = render(events_by_date, source_colors, todos, config)

    # atomic write so the display process never reads a half-written file
    tmp_path = OUTPUT_PATH + ".tmp.png"
    img.save(tmp_path, format="PNG")
    os.replace(tmp_path, OUTPUT_PATH)
    log(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
