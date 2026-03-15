#!/usr/bin/env python3
"""
imsg-search — Search your local iMessage database, safely.
https://github.com/dustindog101/imsg-search
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

from rich import box
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ────────────────────────────────────────────────────────────────────────────
# Theme
# ────────────────────────────────────────────────────────────────────────────

THEME = Theme(
    {
        "banner.title":    "bold bright_cyan",
        "banner.sub":      "dim cyan",
        "banner.ver":      "dim white",
        "flag":            "bold green",
        "flag.desc":       "white",
        "section":         "bold cyan",
        "chat.header":     "bold magenta",
        "chat.ts":         "dim white",
        "chat.me":         "bold bright_blue",
        "chat.them":       "bold bright_yellow",
        "chat.text":       "white",
        "chat.match":      "bold bright_white on dark_orange3",
        "ctx.line":        "dim white",
        "stat.key":        "dim cyan",
        "stat.val":        "bold white",
        "stat.bar":        "cyan",
        "stat.bar2":       "magenta",
        "info":            "cyan",
        "success":         "bold bright_green",
        "warning":         "bold yellow",
        "error":           "bold bright_red",
        "tip":             "dim cyan",
        "dim":             "dim white",
    }
)

console = Console(theme=THEME, highlight=False)

DEFAULT_DB = os.path.expanduser("~/Library/Messages/chat.db")
APPLE_EPOCH = 978307200
VERSION = "1.0.0"

STOP_WORDS = {
    "the","and","for","are","but","not","you","all","can","had","her","was",
    "one","our","out","day","get","has","him","his","how","man","new","now",
    "old","see","two","way","who","boy","did","its","let","put","say","she",
    "too","use","that","with","have","this","will","your","from","they","want",
    "been","good","much","some","time","very","when","come","here","just","like",
    "long","make","many","more","only","over","such","take","than","them","well",
    "also","into","know","most","then","yeah","okay","i'm","it's","don't","can't",
    "i'll","we'll","i've","we're","they're", "lol", "ok", "yea", "nah", "got",
    "gonna","gotta","what","about"
}

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def apple_to_unix(ns: int) -> float:
    return ns / 1e9 + APPLE_EPOCH


def dt_to_apple_ns(dt_str: str, end_of_day=False) -> int:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(dt_str, fmt)
            if end_of_day and fmt == "%Y-%m-%d":
                dt = dt.replace(hour=23, minute=59, second=59)
            return int((dt.timestamp() - APPLE_EPOCH) * 1e9)
        except ValueError:
            pass
    err(f"Cannot parse date [bold]'{dt_str}'[/bold] — use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")


def fmt_ts(apple_ns: int, full=False) -> str:
    dt = datetime.fromtimestamp(apple_to_unix(apple_ns))
    return dt.strftime("%Y-%m-%d %H:%M") if not full else dt.strftime("%A, %B %-d %Y at %-I:%M %p")


def redact(handle: str) -> str:
    if not handle or len(handle) < 5:
        return "***-****"
    return handle[:-4] + "****"


def normalize_handle(handle: str) -> str:
    """Strip spaces; ensure + prefix for phone numbers."""
    h = handle.strip()
    if re.match(r"^\d{10,}$", h):
        h = "+" + h
    return h


def err(msg: str, tip: str = ""):
    console.print(f"\n  [error]✗  Error:[/error] {msg}")
    if tip:
        console.print(f"  [tip]ℹ  {tip}[/tip]")
    console.print()
    sys.exit(1)


def open_db(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        err(
            f"Database not found at [bold]{path}[/bold]",
            "Try passing a custom path with --db PATH",
        )
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        if "unable to open" in str(e).lower() or "permission" in str(e).lower():
            err(
                "Permission denied opening chat.db",
                "Grant Full Disk Access to Terminal in:\n  System Settings › Privacy & Security › Full Disk Access",
            )
        err(f"Could not open database: {e}")


def sparkline(values: list[int]) -> str:
    bars = " ▁▂▃▄▅▆▇█"
    if not values or max(values) == 0:
        return ""
    mx = max(values)
    return "".join(bars[min(8, int(v / mx * 8))] for v in values)

# ────────────────────────────────────────────────────────────────────────────
# Banner + Help
# ────────────────────────────────────────────────────────────────────────────

LOGO = """\
 _ _ __ ___  ___  __ _      ___  ___  __ _ _ __ ___ ___ 
(_) '_ ` _ \\/ __|/ _` |    / __|/ _ \\/ _` | '__/ __/ __|
 | | | | | \\__ \\ (_| |    \\__ \\  __/ (_| | | | (__\\__ \\
 |_|_| |_| |_|___/\\__, |    |___/\\___|\\__,_|_|  \\___|___/
                  |___/                                   """

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOURS_LABEL = [f"{h:02d}" for h in range(24)]


def print_banner():
    console.print()
    console.print(Text(LOGO, style="bold cyan", justify="center"))
    console.print(Text("  search your iMessages from the terminal", style="dim cyan"))
    console.print(Text(f"  v{VERSION}  ·  read-only · safe · composable", style="dim white"))
    console.print()


def print_help():
    print_banner()
    console.print(Rule("[section]USAGE[/section]"))
    console.print()
    console.print(
        "  [flag]imsg-search[/flag] [dim]\\[OPTIONS][/dim]\n\n"
        "  Filters are [bold]optional[/bold] and [bold]fully composable[/bold]. "
        "At least one filter is required.",
    )
    console.print()

    console.print(Rule("[section]SEARCH OPTIONS[/section]"))
    console.print()
    tbl = Table(show_header=False, box=None, padding=(0, 2))
    tbl.add_column(style="flag")
    tbl.add_column(style="dim white")
    tbl.add_column(style="flag.desc")
    rows = [
        ("--text,    -t", "QUERY",  "Search message text (case-insensitive)."),
        ("--contact, -c", "HANDLE", "Filter by phone number or Apple ID."),
        ("--between, -b", "A B",    "Chats where BOTH handles appear."),
        ("--from",        "DATE",   "Start date, inclusive (YYYY-MM-DD)."),
        ("--to",          "DATE",   "End date, inclusive (YYYY-MM-DD)."),
        ("--context, -x", "N",      "Show N surrounding messages per match."),
        ("--limit,   -l", "N",      "Max results  [dim](default: 50)[/dim]."),
    ]
    for f, m, d in rows:
        tbl.add_row(f, m, d)
    console.print(tbl)
    console.print()

    console.print(Rule("[section]STATS OPTIONS[/section]"))
    console.print()
    tbl2 = Table(show_header=False, box=None, padding=(0, 2))
    tbl2.add_column(style="flag")
    tbl2.add_column(style="dim white")
    tbl2.add_column(style="flag.desc")
    tbl2.add_row("--stats, -s", "", "Show analytics for a contact (requires --contact).")
    console.print(tbl2)
    console.print()

    console.print(Rule("[section]OUTPUT OPTIONS[/section]"))
    console.print()
    tbl3 = Table(show_header=False, box=None, padding=(0, 2))
    tbl3.add_column(style="flag")
    tbl3.add_column(style="dim white")
    tbl3.add_column(style="flag.desc")
    out_rows = [
        ("--sort",         "asc|desc", "Sort: asc=oldest first, desc=newest first (default)."),
        ("--json,     -j", "",         "Machine-readable JSON output."),
        ("--redact,   -r", "",         "Mask phone numbers in output."),
        ("--no-banner",    "",         "Suppress the startup banner."),
        ("--db",           "PATH",     "Custom path to chat.db."),
        ("--version,  -V", "",         "Print version and exit."),
        ("--help,     -h", "",         "Show this help page."),
    ]
    for f, m, d in out_rows:
        tbl3.add_row(f, m, d)
    console.print(tbl3)
    console.print()

    console.print(Rule("[section]EXAMPLES[/section]"))
    console.print()
    examples = [
        ("Search by keyword",          'imsg-search --text "fleet street"'),
        ("By contact",                 "imsg-search --contact +12025551234"),
        ("Keyword + contact",          'imsg-search --text "lunch" --contact +12025551234'),
        ("Date range",                 "imsg-search --contact +12025551234 --from 2024-01-01 --to 2024-12-31"),
        ("Context around matches",     'imsg-search --text "hey" --context 3'),
        ("Between two contacts",       "imsg-search --between +12025551234 +19175550000"),
        ("Full contact stats",         "imsg-search --contact +12025551234 --stats"),
        ("JSON pipeline output",       'imsg-search --text "fleet street" --json'),
        ("Redact numbers",             'imsg-search --text "hey" --redact'),
        ("Kitchen sink",               'imsg-search --text "meet" --contact +12025551234 --from 2024-06-01 --context 2 --limit 20'),
    ]
    for label, cmd in examples:
        console.print(f"  [dim]# {label}[/dim]")
        console.print(f"  [bold green]{cmd}[/bold green]")
        console.print()

    console.print(
        Panel(
            "  [tip]• Opens [bold]chat.db[/bold] in read-only mode — can never write or corrupt your messages.\n"
            "  • All queries use [bold]parameterized SQL[/bold] — zero injection risk.\n"
            "  • Requires [bold]Full Disk Access[/bold] in System Settings › Privacy & Security.[/tip]",
            title="[section]SAFETY[/section]",
            border_style="dim cyan",
            padding=(0, 1),
        )
    )
    console.print()

# ────────────────────────────────────────────────────────────────────────────
# Query builder
# ────────────────────────────────────────────────────────────────────────────

def build_search_query(args) -> tuple[str, list]:
    conditions, params = [], []

    if args.text:
        conditions.append("m.text LIKE ?")
        params.append(f"%{args.text}%")

    if args.contact:
        h = normalize_handle(args.contact)
        conditions.append("(h.id = ? OR c.chat_identifier = ?)")
        params.extend([h, h])

    if args.between:
        a, b = normalize_handle(args.between[0]), normalize_handle(args.between[1])
        conditions.append("""
            c.ROWID IN (
                SELECT cmj2.chat_id FROM chat_message_join cmj2
                JOIN message m2 ON cmj2.message_id = m2.ROWID
                JOIN handle h2 ON m2.handle_id = h2.ROWID WHERE h2.id = ?
            )
            AND c.ROWID IN (
                SELECT cmj3.chat_id FROM chat_message_join cmj3
                JOIN message m3 ON cmj3.message_id = m3.ROWID
                JOIN handle h3 ON m3.handle_id = h3.ROWID WHERE h3.id = ?
            )
        """)
        params.extend([a, b])

    if args.from_date:
        conditions.append("m.date >= ?")
        params.append(dt_to_apple_ns(args.from_date))

    if args.to_date:
        conditions.append("m.date <= ?")
        params.append(dt_to_apple_ns(args.to_date, end_of_day=True))

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    # sort: 'asc' = oldest first, 'desc' = newest first (default)
    direction = "ASC" if getattr(args, "sort", "desc") == "asc" else "DESC"

    sql = f"""
        SELECT DISTINCT
            m.ROWID AS message_id, m.date, m.text, m.is_from_me,
            h.id AS sender_handle,
            c.chat_identifier, c.display_name, c.ROWID AS chat_id
        FROM message m
        LEFT JOIN handle h          ON m.handle_id  = h.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID  = cmj.message_id
        LEFT JOIN chat c            ON cmj.chat_id  = c.ROWID
        {where}
        ORDER BY m.date {direction}
        LIMIT ?
    """
    params.append(args.limit)
    return sql, params


def fetch_context(conn, chat_id, msg_id, n):
    before = conn.execute("""
        SELECT m.date, m.text, m.is_from_me, h.id AS sender_handle
        FROM message m
        JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE cmj.chat_id = ? AND m.ROWID < ?
        ORDER BY m.date DESC LIMIT ?
    """, (chat_id, msg_id, n)).fetchall()

    after = conn.execute("""
        SELECT m.date, m.text, m.is_from_me, h.id AS sender_handle
        FROM message m
        JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE cmj.chat_id = ? AND m.ROWID > ?
        ORDER BY m.date ASC LIMIT ?
    """, (chat_id, msg_id, n)).fetchall()

    return list(reversed(before)), list(after)

# ────────────────────────────────────────────────────────────────────────────
# Stats
# ────────────────────────────────────────────────────────────────────────────

def run_stats(conn, handle: str, do_redact: bool):
    h = normalize_handle(handle)
    label = redact(h) if do_redact else h

    rows = conn.execute("""
        SELECT m.date, m.text, m.is_from_me
        FROM message m
        LEFT JOIN handle hn ON m.handle_id = hn.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE hn.id = ? OR c.chat_identifier = ?
        ORDER BY m.date ASC
    """, (h, h)).fetchall()

    if not rows:
        console.print(f"\n  [warning]⚠  No messages found for {label}[/warning]\n")
        return

    sent = [r for r in rows if r["is_from_me"]]
    recv = [r for r in rows if not r["is_from_me"]]
    total = len(rows)

    first_ts = rows[0]["date"]
    last_ts  = rows[-1]["date"]

    # Day of week distribution
    dow_sent  = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).weekday() for r in sent)
    dow_recv  = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).weekday() for r in recv)

    # Hour distribution
    hour_all  = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).hour for r in rows)

    # Monthly volume for sparkline
    month_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        key = datetime.fromtimestamp(apple_to_unix(r["date"])).strftime("%Y-%m")
        month_counts[key] += 1
    sorted_months = sorted(month_counts.keys())
    spark_vals = [month_counts[m] for m in sorted_months]

    # Top words
    def top_words(msg_rows, n=8):
        words = []
        for r in msg_rows:
            if r["text"]:
                for w in re.findall(r"[a-z']+", r["text"].lower()):
                    if w not in STOP_WORDS and len(w) > 2:
                        words.append(w)
        return Counter(words).most_common(n)

    top_sent = top_words(sent)
    top_recv = top_words(recv)

    # ── Print stats ──
    console.print()
    console.print(Panel(
        f"[chat.header]{label}[/chat.header]",
        border_style="magenta", expand=False, padding=(0, 2)
    ))
    console.print()

    # Overview grid
    overview = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
    overview.add_column(style="stat.key")
    overview.add_column(style="stat.val")
    overview.add_column(style="stat.key")
    overview.add_column(style="stat.val")
    overview.add_row(
        "Total messages", f"{total:,}",
        "First message",  fmt_ts(first_ts),
    )
    overview.add_row(
        "You sent",       f"{len(sent):,}   ({len(sent)/total*100:.0f}%)",
        "Last message",   fmt_ts(last_ts),
    )
    overview.add_row(
        "They sent",      f"{len(recv):,}   ({len(recv)/total*100:.0f}%)",
        "Relationship",   f"{(apple_to_unix(last_ts) - apple_to_unix(first_ts)) / 86400:.0f} days",
    )
    console.print(Padding(overview, (0, 2)))

    # Day of week
    console.print(Rule("[section]Activity by Day[/section]"))
    console.print()
    dow_tbl = Table(box=None, show_header=True, padding=(0, 1))
    dow_tbl.add_column("Day",  style="stat.key",  width=5)
    dow_tbl.add_column("You",  style="stat.bar",  width=24)
    dow_tbl.add_column("Them", style="stat.bar2", width=24)
    max_d = max(max((dow_sent.get(i, 0) for i in range(7)), default=1),
                max((dow_recv.get(i, 0) for i in range(7)), default=1), 1)
    for i, day in enumerate(DAYS):
        s = dow_sent.get(i, 0)
        r = dow_recv.get(i, 0)
        bar_s = "█" * int(s / max_d * 20) + f" {s}"
        bar_r = "█" * int(r / max_d * 20) + f" {r}"
        dow_tbl.add_row(day, bar_s, bar_r)
    console.print(Padding(dow_tbl, (0, 2)))
    console.print()

    # Peak hour
    peak_hour = max(hour_all, key=hour_all.get)
    peak_label = f"{peak_hour:02d}:00–{peak_hour:02d}:59"
    hour_vals = [hour_all.get(h, 0) for h in range(24)]
    spark = sparkline(hour_vals)
    console.print(Rule("[section]Hourly Activity[/section]"))
    console.print()
    console.print(f"  [stat.key]Peak hour[/stat.key]  [stat.val]{peak_label}[/stat.val]  ({hour_all[peak_hour]} messages)")
    console.print(f"  [stat.bar]{spark}[/stat.bar]")
    console.print(f"  [dim]00                   12                   23[/dim]")
    console.print()

    # Monthly sparkline
    console.print(Rule("[section]Monthly Volume[/section]"))
    console.print()
    if sorted_months:
        spark2 = sparkline(spark_vals)
        console.print(f"  [stat.bar]{spark2}[/stat.bar]")
        console.print(f"  [dim]{sorted_months[0]}{'':>{max(0, len(spark2)-14)}}{sorted_months[-1]}[/dim]")
    console.print()

    # Top words
    console.print(Rule("[section]Top Words[/section]"))
    console.print()
    word_tbl = Table(box=box.SIMPLE, padding=(0, 2))
    word_tbl.add_column("Your top words",  style="stat.bar",  min_width=20)
    word_tbl.add_column("Their top words", style="stat.bar2", min_width=20)
    max_rows = max(len(top_sent), len(top_recv))
    for i in range(max_rows):
        ws = f"{top_sent[i][0]} ({top_sent[i][1]})" if i < len(top_sent) else ""
        wr = f"{top_recv[i][0]} ({top_recv[i][1]})" if i < len(top_recv) else ""
        word_tbl.add_row(ws, wr)
    console.print(Padding(word_tbl, (0, 2)))
    console.print()

# ────────────────────────────────────────────────────────────────────────────
# Display
# ────────────────────────────────────────────────────────────────────────────

def highlight_match(text: str, query: str) -> Text:
    if not query or not text:
        return Text(text or "[no text]", style="chat.text")
    lo, lq = text.lower(), query.lower()
    result = Text()
    idx = 0
    while True:
        pos = lo.find(lq, idx)
        if pos == -1:
            result.append(text[idx:], style="chat.text")
            break
        result.append(text[idx:pos], style="chat.text")
        result.append(text[pos:pos + len(query)], style="chat.match")
        idx = pos + len(query)
    return result


def render_msg(row, query="", is_ctx=False, do_redact=False):
    ts = fmt_ts(row["date"])
    is_me = row["is_from_me"]
    handle = row["sender_handle"] or ""
    if do_redact and not is_me:
        handle = redact(handle)

    ts_t  = Text(f"[{ts}]", style="chat.ts" if not is_ctx else "dim")
    who   = Text()
    if is_me:
        who.append("  you", style="chat.me" if not is_ctx else "dim")
        who.append("  →  ", style="dim white")
    else:
        who.append(f"  {handle or 'them'}", style="chat.them" if not is_ctx else "dim white")
        who.append("  ·  ", style="dim white")

    body = Text(row["text"] or "[no text]", style="ctx.line") if is_ctx else highlight_match(row["text"] or "[no text]", query)
    console.print(Text.assemble(ts_t, " ", who, body))


def chat_label(row, do_redact) -> str:
    name = row["display_name"] or ""
    ident = row["chat_identifier"] or ""
    label = name if name else ident
    if not label:
        label = row["sender_handle"] or "Unknown"
    return redact(label) if do_redact else label


def print_results_human(rows, conn, args, do_redact):
    query = args.text or ""
    ctx_n = args.context or 0
    seen_ctx: set = set()  # track msg IDs printed as context to avoid dupes

    # Human display always shows oldest→newest within results
    sort = getattr(args, "sort", "desc")
    display_rows = rows if sort == "asc" else list(reversed(rows))

    current_chat = None
    for row in display_rows:
        cid = row["chat_id"]
        if cid != current_chat:
            current_chat = cid
            console.print()
            console.print(Panel(
                f"[chat.header]{chat_label(row, do_redact)}[/chat.header]",
                border_style="magenta", padding=(0, 1), expand=False,
            ))

        if ctx_n and conn:
            befores, afters = fetch_context(conn, cid, row["message_id"], ctx_n)
            for ctx in befores:
                if ctx["date"] not in seen_ctx:
                    render_msg(ctx, is_ctx=True, do_redact=do_redact)
                    seen_ctx.add(ctx["date"])

        render_msg(row, query=query, do_redact=do_redact)

        if ctx_n and conn:
            for ctx in afters:
                if ctx["date"] not in seen_ctx:
                    render_msg(ctx, is_ctx=True, do_redact=do_redact)
                    seen_ctx.add(ctx["date"])
            console.print("  [dim]╌╌╌[/dim]")

    console.print()


def print_results_json(rows, do_redact, sort="desc"):
    # rows come from DB in query sort order; emit them as-is — consistent with --sort flag
    # asc = rows already oldest→newest; desc = rows already newest→oldest
    out = []
    for row in rows:
        sender = row["sender_handle"] or ""
        ident  = row["chat_identifier"] or ""
        if do_redact:
            if not row["is_from_me"]:
                sender = redact(sender)
            ident = redact(ident)
        out.append({
            "timestamp":      fmt_ts(row["date"]),
            "chat_identifier": ident,
            "chat_name":       row["display_name"] or "",
            "sender":          sender,
            "is_from_me":      bool(row["is_from_me"]),
            "text":            row["text"] or "",
        })
    print(json.dumps(out, indent=2))


def print_summary(args, count):
    parts = []
    if args.text:    parts.append(f"text=[bold]'{args.text}'[/bold]")
    if args.contact: parts.append(f"contact=[bold]{args.contact}[/bold]")
    if args.between: parts.append(f"between=[bold]{args.between[0]}[/bold] & [bold]{args.between[1]}[/bold]")
    if args.from_date: parts.append(f"from=[bold]{args.from_date}[/bold]")
    if args.to_date:   parts.append(f"to=[bold]{args.to_date}[/bold]")

    rc = "success" if count > 0 else "warning"
    result = f"[{rc}]{count} result{'s' if count != 1 else ''}[/{rc}]"
    console.print(Panel(
        f"{result}  [dim]·[/dim]  {'  '.join(parts)}",
        border_style="dim cyan", padding=(0, 1), expand=False,
    ))
    console.print()

# ────────────────────────────────────────────────────────────────────────────
# Argument parser
# ────────────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="imsg-search", add_help=False)
    p.add_argument("--text",    "-t", metavar="QUERY")
    p.add_argument("--contact", "-c", metavar="HANDLE")
    p.add_argument("--between", "-b", nargs=2, metavar=("A", "B"))
    p.add_argument("--from",    dest="from_date", metavar="DATE")
    p.add_argument("--to",      dest="to_date",   metavar="DATE")
    p.add_argument("--context", "-x", type=int, default=0, metavar="N")
    p.add_argument("--limit",   "-l", type=int, default=50, metavar="N")
    p.add_argument("--stats",   "-s", action="store_true")
    p.add_argument("--sort",    choices=["asc", "desc"], default="desc",
                   help="Sort order: asc=oldest first, desc=newest first (default)")
    p.add_argument("--json",    "-j", dest="as_json", action="store_true")
    p.add_argument("--redact",  "-r", action="store_true")
    p.add_argument("--db",      metavar="PATH", default=DEFAULT_DB)
    p.add_argument("--no-banner", dest="no_banner", action="store_true")
    p.add_argument("--version", "-V", action="store_true")
    p.add_argument("--help",    "-h", action="store_true")
    return p

# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main():
    parser = build_parser()
    args   = parser.parse_args()

    show_banner = not args.no_banner and not args.as_json

    if args.version:
        console.print(f"[dim]imsg-search[/dim] [bold cyan]v{VERSION}[/bold cyan]")
        sys.exit(0)

    if args.help or len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    if show_banner:
        print_banner()

    # Stats mode — only needs --contact
    if args.stats:
        if not args.contact:
            err("--stats requires --contact HANDLE", "e.g. imsg-search --contact +12025551234 --stats")
        conn = open_db(args.db)
        run_stats(conn, args.contact, args.redact)
        conn.close()
        return

    has_filter = any([args.text, args.contact, args.between, args.from_date, args.to_date])
    if not has_filter:
        console.print(Panel(
            "[warning]At least one search filter is required.[/warning]\n\n"
            "[tip]Run [bold]imsg-search --help[/bold] to see all options.[/tip]",
            border_style="yellow", padding=(0, 2),
        ))
        console.print()
        sys.exit(1)

    conn = open_db(args.db)

    if show_banner:
        console.print(Rule("[dim]searching[/dim]"))
        console.print()

    sql, params = build_search_query(args)
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        err(f"Query failed: {e}")

    if args.as_json:
        print_results_json(rows, args.redact, sort=args.sort)
        conn.close()
        return

    print_results_human(rows, conn if args.context else None, args, args.redact)
    conn.close()
    print_summary(args, len(rows))


if __name__ == "__main__":
    main()
