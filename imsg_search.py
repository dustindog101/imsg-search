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
        "stat.bar3":       "green",
        "stat.bar4":       "yellow",
        "stat.bar5":       "bright_red",
        "stat.bar6":       "bright_blue",
        "info":            "cyan",
        "success":         "bold bright_green",
        "warning":         "bold yellow",
        "error":           "bold bright_red",
        "tip":             "dim cyan",
        "dim":             "dim white",
        "group.icon":      "bold bright_green",
    }
)

MEMBER_STYLES = ["stat.bar", "stat.bar2", "stat.bar3", "stat.bar4", "stat.bar5", "stat.bar6"]

console = Console(theme=THEME, highlight=False)

DEFAULT_DB = os.path.expanduser("~/Library/Messages/chat.db")
APPLE_EPOCH = 978307200
VERSION = "1.2.0"

# Filter out tapbacks, empty messages, and attachment-only rows
REAL_MSG_FILTER = "(m.associated_message_type = 0 OR m.associated_message_type IS NULL) AND m.text IS NOT NULL AND m.text != ''"

REACTION_MAP = {
    2000: ("❤️ ", "Loved"),
    2001: ("👍", "Liked"),
    2002: ("👎", "Disliked"),
    2003: ("😂", "Laughed"),
    2004: ("❗", "Emphasized"),
    2005: ("❓", "Questioned"),
}

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

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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
        err(f"Database not found at [bold]{path}[/bold]", "Try --db PATH")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        if "unable to open" in str(e).lower() or "permission" in str(e).lower():
            err("Permission denied opening chat.db",
                "Grant Full Disk Access to Terminal in:\n  System Settings › Privacy & Security › Full Disk Access")
        err(f"Could not open database: {e}")


def sparkline(values: list[int]) -> str:
    bars = " ▁▂▃▄▅▆▇█"
    if not values or max(values) == 0:
        return ""
    mx = max(values)
    return "".join(bars[min(8, int(v / mx * 8))] for v in values)


def top_words(msg_rows, n=8):
    words = []
    for r in msg_rows:
        txt = r["text"] if isinstance(r, sqlite3.Row) else r.get("text")
        if txt:
            for w in re.findall(r"[a-z']+", txt.lower()):
                if w not in STOP_WORDS and len(w) > 2:
                    words.append(w)
    return Counter(words).most_common(n)

# ────────────────────────────────────────────────────────────────────────────
# Group chat resolution
# ────────────────────────────────────────────────────────────────────────────

def resolve_group(conn, query: str) -> tuple[int, str]:
    """Find a group chat by name or identifier. Returns (chat_id, display_label).
    Exits with error if 0 or >1 matches (with disambiguation table)."""

    # Try exact chat_identifier match first
    row = conn.execute(
        "SELECT ROWID, display_name, chat_identifier FROM chat WHERE chat_identifier = ? AND style = 43",
        (query,),
    ).fetchone()
    if row:
        label = row["display_name"] or row["chat_identifier"]
        return row["ROWID"], label

    # Try case-insensitive display_name LIKE match
    rows = conn.execute(
        "SELECT ROWID, display_name, chat_identifier FROM chat WHERE LOWER(display_name) LIKE ? AND style = 43",
        (f"%{query.lower()}%",),
    ).fetchall()

    if len(rows) == 1:
        r = rows[0]
        return r["ROWID"], r["display_name"] or r["chat_identifier"]

    if len(rows) == 0:
        err(f"No group chat found matching [bold]'{query}'[/bold]",
            "Use --list-groups to see all your group chats")

    # Disambiguation: multiple matches
    console.print(f"\n  [warning]⚠  Multiple groups match '{query}':[/warning]\n")
    tbl = Table(box=box.ROUNDED, border_style="yellow", padding=(0, 1))
    tbl.add_column("#", style="dim white", width=4)
    tbl.add_column("Name", style="chat.header")
    tbl.add_column("Chat ID", style="dim white")
    for i, r in enumerate(rows[:15], 1):
        tbl.add_row(str(i), r["display_name"] or "(unnamed)", r["chat_identifier"])
    console.print(Padding(tbl, (0, 2)))
    console.print(f"\n  [tip]Be more specific, or use the exact chat identifier:[/tip]")
    console.print(f"  [flag]imsg-search --group \"{rows[0]['chat_identifier']}\" ...[/flag]\n")
    sys.exit(1)


def get_group_members(conn, chat_id: int) -> list[str]:
    """Get list of phone/email handles in a group chat."""
    rows = conn.execute("""
        SELECT DISTINCT h.id
        FROM chat_handle_join chj
        JOIN handle h ON chj.handle_id = h.ROWID
        WHERE chj.chat_id = ?
    """, (chat_id,)).fetchall()
    return [r["id"] for r in rows]

# ────────────────────────────────────────────────────────────────────────────
# List groups
# ────────────────────────────────────────────────────────────────────────────

def run_list_groups(conn, limit: int, do_redact: bool):
    rows = conn.execute("""
        SELECT c.ROWID as chat_id, c.display_name, c.chat_identifier,
               COUNT(DISTINCT chj.handle_id) as member_count,
               COUNT(DISTINCT cmj.message_id) as msg_count,
               MAX(m.date) as last_active
        FROM chat c
        JOIN chat_handle_join chj ON c.ROWID = chj.chat_id
        JOIN chat_message_join cmj ON c.ROWID = cmj.chat_id
        JOIN message m ON cmj.message_id = m.ROWID
        WHERE c.style = 43
        GROUP BY c.ROWID
        ORDER BY last_active DESC
        LIMIT ?
    """, (limit,)).fetchall()

    if not rows:
        console.print("\n  [warning]⚠  No group chats found.[/warning]\n")
        return

    console.print()
    tbl = Table(
        title="[section]👥 Group Chats[/section]",
        box=box.ROUNDED,
        border_style="cyan",
        padding=(0, 1),
        title_justify="left",
    )
    tbl.add_column("#", style="dim white", width=4)
    tbl.add_column("Name", style="chat.header", min_width=20)
    tbl.add_column("Members", style="stat.val", justify="right", width=8)
    tbl.add_column("Messages", style="stat.val", justify="right", width=10)
    tbl.add_column("Last Active", style="chat.ts", width=18)
    tbl.add_column("Chat ID", style="dim white", max_width=30)

    for i, r in enumerate(rows, 1):
        name = r["display_name"] or "(unnamed)"
        cid = r["chat_identifier"]
        if do_redact:
            name = name[:3] + "***" if len(name) > 3 else "***"
        tbl.add_row(
            str(i),
            name,
            f"{r['member_count']}",
            f"{r['msg_count']:,}",
            fmt_ts(r["last_active"]),
            cid if not do_redact else cid[:12] + "...",
        )

    console.print(Padding(tbl, (0, 2)))
    console.print(f"\n  [tip]Use a group name or chat ID with --group to search within it.[/tip]")
    console.print(f"  [dim]Example: imsg-search --group \"{rows[0]['display_name'] or rows[0]['chat_identifier']}\" --text \"hello\"[/dim]\n")

# ────────────────────────────────────────────────────────────────────────────
# Banner + Help
# ────────────────────────────────────────────────────────────────────────────

LOGO = """\
 _ _ __ ___  ___  __ _      ___  ___  __ _ _ __ ___ ___ 
(_) '_ ` _ \\/ __|/ _` |    / __|/ _ \\/ _` | '__/ __/ __|
 | | | | | \\__ \\ (_| |    \\__ \\  __/ (_| | | | (__\\__ \\
 |_|_| |_| |_|___/\\__, |    |___/\\___|\\__,_|_|  \\___|___/
                  |___/                                   """


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
        ("--contact, -c", "HANDLE", "Filter by phone number or Apple ID (DMs)."),
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

    console.print(Rule("[section]GROUP CHAT OPTIONS[/section]"))
    console.print()
    tbl_g = Table(show_header=False, box=None, padding=(0, 2))
    tbl_g.add_column(style="flag")
    tbl_g.add_column(style="dim white")
    tbl_g.add_column(style="flag.desc")
    tbl_g.add_row("--list-groups",    "",       "List all group chats (ranked by activity).")
    tbl_g.add_row("--group, -g",      "NAME",   "Search within a group chat (name or chat ID).")
    tbl_g.add_row("--member, -m",     "HANDLE", "Filter to a participant within a group.")
    console.print(tbl_g)
    console.print()

    console.print(Rule("[section]STATS & OUTPUT OPTIONS[/section]"))
    console.print()
    tbl2 = Table(show_header=False, box=None, padding=(0, 2))
    tbl2.add_column(style="flag")
    tbl2.add_column(style="dim white")
    tbl2.add_column(style="flag.desc")
    out_rows = [
        ("--stats,     -s", "",         "Analytics: no args=personal, with --contact or --group=targeted."),
        ("--deep,      -d", "",         "Deeper analysis for --stats (per-member words, peak hours, etc.)."),
        ("--reactions",     "",         "Reaction report for a contact or group."),
        ("--sort",          "asc|desc", "Sort: asc=oldest first, desc=newest first."),
        ("--json,      -j", "",         "Machine-readable JSON output."),
        ("--redact,    -r", "",         "Mask phone numbers in output."),
        ("--no-banner",     "",         "Suppress the startup banner."),
        ("--db",            "PATH",     "Custom path to chat.db."),
        ("--version,   -V", "",         "Print version and exit."),
        ("--help,      -h", "",         "Show this help page."),
    ]
    for f, m, d in out_rows:
        tbl2.add_row(f, m, d)
    console.print(tbl2)
    console.print()

    console.print(Rule("[section]EXAMPLES[/section]"))
    console.print()
    examples = [
        ("Search by keyword",          'imsg-search --text "fleet street"'),
        ("By contact",                 "imsg-search --contact +12025551234"),
        ("Keyword + contact + date",   'imsg-search --text "lunch" --contact +12025551234 --from 2024-01-01'),
        ("Context around matches",     'imsg-search --text "hey" --context 3'),
        ("Contact stats",             "imsg-search --contact +12025551234 --stats"),
        ("List all group chats",       "imsg-search --list-groups"),
        ('Search within a group',      'imsg-search --group "Warriors" --text "tomorrow"'),
        ("Filter by group member",     'imsg-search --group "Warriors" --member +12025551234'),
        ("Group stats",                'imsg-search --group "Warriors" --stats'),
        ("JSON pipeline output",       'imsg-search --text "fleet street" --json --sort asc'),
        ("Redact numbers",             'imsg-search --text "hey" --redact'),
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

def build_search_query(args, group_chat_id=None) -> tuple[str, list]:
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

    if group_chat_id is not None:
        conditions.append("c.ROWID = ?")
        params.append(group_chat_id)

    if getattr(args, "member", None):
        h = normalize_handle(args.member)
        conditions.append("h.id = ?")
        params.append(h)

    if args.from_date:
        conditions.append("m.date >= ?")
        params.append(dt_to_apple_ns(args.from_date))

    if args.to_date:
        conditions.append("m.date <= ?")
        params.append(dt_to_apple_ns(args.to_date, end_of_day=True))

    # Always exclude reactions and empty messages from search results
    conditions.append(REAL_MSG_FILTER)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

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
# Stats — DM
# ────────────────────────────────────────────────────────────────────────────

def fetch_reactions(conn, handle=None, group_chat_id=None):
    """Fetch reaction counts split by is_from_me."""
    if handle:
        h = normalize_handle(handle)
        return conn.execute("""
            SELECT m.associated_message_type AS rtype, m.is_from_me, COUNT(*) as cnt
            FROM message m
            LEFT JOIN handle hn ON m.handle_id = hn.ROWID
            LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            LEFT JOIN chat c ON cmj.chat_id = c.ROWID
            WHERE (hn.id = ? OR c.chat_identifier = ?)
            AND m.associated_message_type BETWEEN 2000 AND 2005
            GROUP BY m.associated_message_type, m.is_from_me
        """, (h, h)).fetchall()
    elif group_chat_id:
        return conn.execute("""
            SELECT m.associated_message_type AS rtype, m.is_from_me,
                   h.id AS sender_handle, COUNT(*) as cnt
            FROM message m
            JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            LEFT JOIN handle h ON m.handle_id = h.ROWID
            WHERE cmj.chat_id = ?
            AND m.associated_message_type BETWEEN 2000 AND 2005
            GROUP BY m.associated_message_type, m.is_from_me, h.id
        """, (group_chat_id,)).fetchall()
    return []


def print_reactions_dm(reaction_rows, do_redact):
    """Print reaction analytics for a DM contact."""
    if not reaction_rows:
        return
    mine: Counter = Counter()
    theirs: Counter = Counter()
    for r in reaction_rows:
        if r["is_from_me"]:
            mine[r["rtype"]] += r["cnt"]
        else:
            theirs[r["rtype"]] += r["cnt"]
    total_r = sum(mine.values()) + sum(theirs.values())
    if total_r == 0:
        return
    console.print(Rule("[section]Reactions[/section]"))
    console.print()
    max_r = max(list(mine.values()) + list(theirs.values()) + [1])
    react_tbl = Table(box=box.SIMPLE, padding=(0, 2))
    react_tbl.add_column("Their reactions to you", style="stat.bar",  min_width=28)
    react_tbl.add_column("Your reactions to them", style="stat.bar2", min_width=28)
    for rtype, (emoji, label) in REACTION_MAP.items():
        t = theirs.get(rtype, 0)
        m = mine.get(rtype, 0)
        if t == 0 and m == 0:
            continue
        bar_t = f"{emoji} {label:<10} {'█' * int(t/max_r*15)} {t}" if t else ""
        bar_m = f"{emoji} {label:<10} {'█' * int(m/max_r*15)} {m}" if m else ""
        react_tbl.add_row(bar_t, bar_m)
    console.print(Padding(react_tbl, (0, 2)))
    console.print()


def print_reactions_group(reaction_rows, members, do_redact):
    """Print per-member reactor table for a group."""
    if not reaction_rows:
        return
    # member -> {rtype: count}
    member_reacts: dict[str, Counter] = defaultdict(Counter)
    for r in reaction_rows:
        if r["is_from_me"]:
            member_reacts["you"][r["rtype"]] += r["cnt"]
        else:
            handle = r["sender_handle"] or "unknown"
            key = redact(handle) if do_redact else handle
            member_reacts[key][r["rtype"]] += r["cnt"]
    if not member_reacts:
        return
    console.print(Rule("[section]Top Reactors[/section]"))
    console.print()
    reactor_tbl = Table(box=None, show_header=False, padding=(0, 1))
    reactor_tbl.add_column("Member", style="stat.key", min_width=18)
    reactor_tbl.add_column("Reactions", style="stat.bar")
    top_reactors = sorted(member_reacts.items(), key=lambda x: sum(x[1].values()), reverse=True)[:10]
    for member, counts in top_reactors:
        parts = []
        for rtype, (emoji, _) in REACTION_MAP.items():
            c = counts.get(rtype, 0)
            if c:
                parts.append(f"{emoji} {c}")
        reactor_tbl.add_row(member, "  ".join(parts))
    console.print(Padding(reactor_tbl, (0, 2)))
    console.print()


def run_stats_self(conn, do_redact: bool, deep: bool = False):
    """Personal dashboard — shown when --stats used with no --contact or --group."""
    console.print()
    console.print(Panel(
        "[group.icon]📱[/group.icon]  [chat.header]Your iMessage Overview[/chat.header]",
        border_style="magenta", expand=False, padding=(0, 2),
    ))
    console.print()

    total = conn.execute(f"SELECT COUNT(*) FROM message m WHERE {REAL_MSG_FILTER}").fetchone()[0]
    dms   = conn.execute("SELECT COUNT(*) FROM chat WHERE style = 45").fetchone()[0]
    groups= conn.execute("SELECT COUNT(*) FROM chat WHERE style = 43").fetchone()[0]
    row   = conn.execute(f"SELECT MIN(m.date), MAX(m.date) FROM message m WHERE {REAL_MSG_FILTER}").fetchone()
    since = fmt_ts(row[0]) if row[0] else "unknown"

    ov = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
    ov.add_column(style="stat.key"); ov.add_column(style="stat.val")
    ov.add_column(style="stat.key"); ov.add_column(style="stat.val")
    ov.add_row("Total messages", f"{total:,}",  "DM conversations",  f"{dms:,}")
    ov.add_row("Group chats",    f"{groups:,}", "Messaging since",   since)
    console.print(Padding(ov, (0, 2)))

    # Top contacts
    top_contacts = conn.execute(f"""
        SELECT h.id, COUNT(*) as cnt FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE {REAL_MSG_FILTER} AND h.id IS NOT NULL AND m.is_from_me = 0
        GROUP BY h.id ORDER BY cnt DESC LIMIT 6
    """).fetchall()
    if top_contacts:
        console.print(Rule("[section]Top Contacts[/section]"))
        console.print()
        max_c = top_contacts[0]["cnt"]
        ct = Table(box=None, show_header=False, padding=(0, 1))
        ct.add_column(style="stat.key", min_width=18)
        ct.add_column(style="stat.bar", min_width=30)
        ct.add_column(style="stat.val", justify="right", width=8)
        for idx, r in enumerate(top_contacts):
            style = MEMBER_STYLES[idx % len(MEMBER_STYLES)]
            bar = "█" * int(r["cnt"] / max_c * 25)
            handle = redact(r["id"]) if do_redact else r["id"]
            ct.add_row(handle, f"[{style}]{bar}[/{style}]", f"{r['cnt']:,}")
        console.print(Padding(ct, (0, 2)))
        console.print()

    # Top groups
    top_groups = conn.execute(f"""
        SELECT c.display_name, c.chat_identifier,
               COUNT(DISTINCT chj.handle_id) as members,
               COUNT(DISTINCT cmj.message_id) as cnt
        FROM chat c
        JOIN chat_handle_join chj ON c.ROWID = chj.chat_id
        JOIN chat_message_join cmj ON c.ROWID = cmj.chat_id
        JOIN message m ON cmj.message_id = m.ROWID
        WHERE c.style = 43 AND {REAL_MSG_FILTER}
        GROUP BY c.ROWID ORDER BY cnt DESC LIMIT 5
    """).fetchall()
    if top_groups:
        console.print(Rule("[section]Top Groups[/section]"))
        console.print()
        max_g = top_groups[0]["cnt"]
        gt = Table(box=None, show_header=False, padding=(0, 1))
        gt.add_column(style="stat.key", min_width=22)
        gt.add_column(style="stat.bar2", min_width=30)
        gt.add_column(style="stat.val", justify="right", width=8)
        for r in top_groups:
            name = r["display_name"] or r["chat_identifier"][:16] + "..."
            bar = "█" * int(r["cnt"] / max_g * 25)
            gt.add_row(f"{name}  [dim]({r['members']}👥)[/dim]", f"[stat.bar2]{bar}[/stat.bar2]", f"{r['cnt']:,}")
        console.print(Padding(gt, (0, 2)))
        console.print()

    # Yearly sparkline
    year_rows = conn.execute(f"""
        SELECT strftime('%Y-%m', datetime(m.date/1000000000 + {APPLE_EPOCH}, 'unixepoch')) as mo, COUNT(*) as cnt
        FROM message m WHERE {REAL_MSG_FILTER} GROUP BY mo ORDER BY mo
    """).fetchall()
    if year_rows:
        months = [r["mo"] for r in year_rows]
        vals   = [r["cnt"] for r in year_rows]
        console.print(Rule("[section]Monthly Volume[/section]"))
        console.print()
        s = sparkline(vals)
        console.print(f"  [stat.bar]{s}[/stat.bar]")
        console.print(f"  [dim]{months[0]}{'':{max(0,len(s)-14)}}{months[-1]}[/dim]")
        console.print()

    if deep:
        # Global top words
        all_rows = conn.execute(f"SELECT text FROM message m WHERE {REAL_MSG_FILTER} AND m.is_from_me = 1").fetchall()
        tw = top_words(all_rows, n=12)
        if tw:
            console.print(Rule("[section]Your Most-Used Words[/section]"))
            console.print()
            wl = "  ".join(f"[stat.bar]{w}[/stat.bar] [dim]({c})[/dim]" for w, c in tw)
            console.print(f"  {wl}")
            console.print()

        # Busiest hour
        hour_rows = conn.execute(f"""
            SELECT strftime('%H', datetime(m.date/1000000000 + {APPLE_EPOCH}, 'unixepoch')) as hr, COUNT(*) as cnt
            FROM message m WHERE {REAL_MSG_FILTER} GROUP BY hr
        """).fetchall()
        hour_dict = {int(r["hr"]): r["cnt"] for r in hour_rows}
        hvals = [hour_dict.get(h, 0) for h in range(24)]
        peak  = max(range(24), key=lambda h: hour_dict.get(h, 0))
        console.print(Rule("[section]Your Busiest Hour[/section]"))
        console.print()
        console.print(f"  [stat.key]Peak hour[/stat.key]  [stat.val]{peak:02d}:00–{peak:02d}:59[/stat.val]  ({hour_dict.get(peak,0):,} messages)")
        console.print(f"  [stat.bar]{sparkline(hvals)}[/stat.bar]")
        console.print(f"  [dim]00                   12                   23[/dim]")
        console.print()

    console.print(f"  [tip]imsg-search --help for all options[/tip]")
    console.print()


def run_stats_dm(conn, handle: str, do_redact: bool, deep: bool = False):
    h = normalize_handle(handle)
    label = redact(h) if do_redact else h

    rows = conn.execute(f"""
        SELECT m.date, m.text, m.is_from_me FROM message m
        LEFT JOIN handle hn ON m.handle_id = hn.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE (hn.id = ? OR c.chat_identifier = ?) AND {REAL_MSG_FILTER}
        ORDER BY m.date ASC
    """, (h, h)).fetchall()

    if not rows:
        console.print(f"\n  [warning]⚠  No messages found for {label}[/warning]\n")
        return

    sent = [r for r in rows if r["is_from_me"]]
    recv = [r for r in rows if not r["is_from_me"]]
    total = len(rows)
    first_ts, last_ts = rows[0]["date"], rows[-1]["date"]

    dow_sent = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).weekday() for r in sent)
    dow_recv = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).weekday() for r in recv)
    hour_all = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).hour for r in rows)

    month_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        month_counts[datetime.fromtimestamp(apple_to_unix(r["date"])).strftime("%Y-%m")] += 1
    sorted_months = sorted(month_counts.keys())
    spark_vals = [month_counts[m] for m in sorted_months]

    top_sent = top_words(sent)
    top_recv = top_words(recv)

    # Print
    console.print()
    console.print(Panel(f"[chat.header]{label}[/chat.header]", border_style="magenta", expand=False, padding=(0, 2)))
    console.print()

    ov = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
    ov.add_column(style="stat.key"); ov.add_column(style="stat.val")
    ov.add_column(style="stat.key"); ov.add_column(style="stat.val")
    ov.add_row("Total messages", f"{total:,}",      "First message", fmt_ts(first_ts))
    ov.add_row("You sent",      f"{len(sent):,}   ({len(sent)/total*100:.0f}%)", "Last message", fmt_ts(last_ts))
    ov.add_row("They sent",     f"{len(recv):,}   ({len(recv)/total*100:.0f}%)", "Relationship", f"{(apple_to_unix(last_ts)-apple_to_unix(first_ts))/86400:.0f} days")
    console.print(Padding(ov, (0, 2)))

    # Day of week
    console.print(Rule("[section]Activity by Day[/section]"))
    console.print()
    dow_tbl = Table(box=None, show_header=True, padding=(0, 1))
    dow_tbl.add_column("Day", style="stat.key", width=5)
    dow_tbl.add_column("You", style="stat.bar", width=24)
    dow_tbl.add_column("Them", style="stat.bar2", width=24)
    max_d = max(max((dow_sent.get(i, 0) for i in range(7)), default=1), max((dow_recv.get(i, 0) for i in range(7)), default=1), 1)
    for i, day in enumerate(DAYS):
        s, r = dow_sent.get(i, 0), dow_recv.get(i, 0)
        dow_tbl.add_row(day, "█" * int(s / max_d * 20) + f" {s}", "█" * int(r / max_d * 20) + f" {r}")
    console.print(Padding(dow_tbl, (0, 2)))
    console.print()

    # Hour
    peak_hour = max(hour_all, key=hour_all.get)
    hour_vals = [hour_all.get(h, 0) for h in range(24)]
    console.print(Rule("[section]Hourly Activity[/section]"))
    console.print()
    console.print(f"  [stat.key]Peak hour[/stat.key]  [stat.val]{peak_hour:02d}:00–{peak_hour:02d}:59[/stat.val]  ({hour_all[peak_hour]} messages)")
    console.print(f"  [stat.bar]{sparkline(hour_vals)}[/stat.bar]")
    console.print(f"  [dim]00                   12                   23[/dim]")
    console.print()

    # Monthly
    console.print(Rule("[section]Monthly Volume[/section]"))
    console.print()
    if sorted_months:
        s2 = sparkline(spark_vals)
        console.print(f"  [stat.bar]{s2}[/stat.bar]")
        console.print(f"  [dim]{sorted_months[0]}{'':{max(0, len(s2)-14)}}{sorted_months[-1]}[/dim]")
    console.print()

    # Words
    console.print(Rule("[section]Top Words[/section]"))
    console.print()
    word_tbl = Table(box=box.SIMPLE, padding=(0, 2))
    word_tbl.add_column("Your top words", style="stat.bar", min_width=20)
    word_tbl.add_column("Their top words", style="stat.bar2", min_width=20)
    for i in range(max(len(top_sent), len(top_recv))):
        ws = f"{top_sent[i][0]} ({top_sent[i][1]})" if i < len(top_sent) else ""
        wr = f"{top_recv[i][0]} ({top_recv[i][1]})" if i < len(top_recv) else ""
        word_tbl.add_row(ws, wr)
    console.print(Padding(word_tbl, (0, 2)))
    console.print()

    # Reactions
    reaction_rows = fetch_reactions(conn, handle=handle)
    print_reactions_dm(reaction_rows, do_redact)

# ────────────────────────────────────────────────────────────────────────────
# Stats — Group
# ────────────────────────────────────────────────────────────────────────────

def run_stats_group(conn, chat_id: int, group_name: str, do_redact: bool, deep: bool = False):
    members = get_group_members(conn, chat_id)

    rows = conn.execute(f"""
        SELECT m.date, m.text, m.is_from_me, h.id AS sender_handle
        FROM message m
        JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE cmj.chat_id = ? AND {REAL_MSG_FILTER}
        ORDER BY m.date ASC
    """, (chat_id,)).fetchall()

    if not rows:
        console.print(f"\n  [warning]⚠  No messages found in {group_name}[/warning]\n")
        return

    total = len(rows)
    first_ts, last_ts = rows[0]["date"], rows[-1]["date"]

    # Per-member message counts
    member_counts: Counter = Counter()
    for r in rows:
        if r["is_from_me"]:
            member_counts["you"] += 1
        else:
            handle = r["sender_handle"] or "unknown"
            member_counts[redact(handle) if do_redact else handle] += 1

    # Day of week
    dow_all = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).weekday() for r in rows)
    hour_all = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).hour for r in rows)

    # Monthly
    month_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        month_counts[datetime.fromtimestamp(apple_to_unix(r["date"])).strftime("%Y-%m")] += 1
    sorted_months = sorted(month_counts.keys())
    spark_vals = [month_counts[m] for m in sorted_months]

    # Print
    label = redact(group_name) if do_redact else group_name
    console.print()
    console.print(Panel(
        f"[group.icon]👥[/group.icon]  [chat.header]{label}[/chat.header]  [dim]({len(members)} members)[/dim]",
        border_style="magenta", expand=False, padding=(0, 2),
    ))
    console.print()

    ov = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
    ov.add_column(style="stat.key"); ov.add_column(style="stat.val")
    ov.add_column(style="stat.key"); ov.add_column(style="stat.val")
    ov.add_row("Total messages", f"{total:,}",          "First message", fmt_ts(first_ts))
    ov.add_row("Members",        f"{len(members)}",     "Last message", fmt_ts(last_ts))
    days_active = (apple_to_unix(last_ts) - apple_to_unix(first_ts)) / 86400
    ov.add_row("Avg msgs/day",   f"{total/max(days_active,1):.1f}", "Active for", f"{days_active:.0f} days")
    console.print(Padding(ov, (0, 2)))

    # Member distribution
    console.print(Rule("[section]Message Distribution[/section]"))
    console.print()
    dist_tbl = Table(box=None, show_header=False, padding=(0, 1))
    dist_tbl.add_column("Member", style="stat.key", min_width=18)
    dist_tbl.add_column("Bar", min_width=30)
    dist_tbl.add_column("Count", style="stat.val", justify="right", width=12)
    max_c = max(member_counts.values()) if member_counts else 1
    for idx, (member, count) in enumerate(member_counts.most_common(15)):
        pct = count / total * 100
        style = MEMBER_STYLES[idx % len(MEMBER_STYLES)]
        bar = "█" * int(count / max_c * 25)
        dist_tbl.add_row(member, f"[{style}]{bar}[/{style}]", f"{count:,}  ({pct:.0f}%)")
    console.print(Padding(dist_tbl, (0, 2)))
    console.print()

    # Day of week
    console.print(Rule("[section]Activity by Day[/section]"))
    console.print()
    dow_tbl = Table(box=None, show_header=True, padding=(0, 1))
    dow_tbl.add_column("Day", style="stat.key", width=5)
    dow_tbl.add_column("Messages", style="stat.bar", width=30)
    max_d = max(dow_all.values()) if dow_all else 1
    for i, day in enumerate(DAYS):
        c = dow_all.get(i, 0)
        dow_tbl.add_row(day, "█" * int(c / max_d * 25) + f" {c}")
    console.print(Padding(dow_tbl, (0, 2)))
    console.print()

    # Hour
    peak_hour = max(hour_all, key=hour_all.get) if hour_all else 0
    hour_vals = [hour_all.get(h, 0) for h in range(24)]
    console.print(Rule("[section]Hourly Activity[/section]"))
    console.print()
    console.print(f"  [stat.key]Peak hour[/stat.key]  [stat.val]{peak_hour:02d}:00–{peak_hour:02d}:59[/stat.val]  ({hour_all.get(peak_hour,0)} messages)")
    console.print(f"  [stat.bar]{sparkline(hour_vals)}[/stat.bar]")
    console.print(f"  [dim]00                   12                   23[/dim]")
    console.print()

    # Monthly
    console.print(Rule("[section]Monthly Volume[/section]"))
    console.print()
    if sorted_months:
        s2 = sparkline(spark_vals)
        console.print(f"  [stat.bar]{s2}[/stat.bar]")
        console.print(f"  [dim]{sorted_months[0]}{'':{max(0, len(s2)-14)}}{sorted_months[-1]}[/dim]")
    console.print()

    # Top words (group-wide)
    console.print(Rule("[section]Top Words (group-wide)[/section]"))
    console.print()
    tw = top_words(rows, n=10)
    if tw:
        word_line = "  ".join(f"[stat.bar]{w}[/stat.bar] [dim]({c})[/dim]" for w, c in tw)
        console.print(f"  {word_line}")
    console.print()

    # Reactions (always show in group stats)
    reaction_rows = fetch_reactions(conn, group_chat_id=chat_id)
    print_reactions_group(reaction_rows, members, do_redact)

    if deep:
        # Per-member top words
        console.print(Rule("[section]Per-Member Top Words[/section]"))
        console.print()
        member_msgs: dict[str, list] = defaultdict(list)
        for r in rows:
            key = "you" if r["is_from_me"] else (redact(r["sender_handle"] or "?") if do_redact else (r["sender_handle"] or "unknown"))
            member_msgs[key].append(r)
        wt = Table(box=box.SIMPLE, padding=(0, 1))
        members_shown = list(member_msgs.keys())[:4]
        for m in members_shown:
            wt.add_column(m, style="stat.bar", min_width=18)
        max_rows_w = max(len(top_words(member_msgs[m], n=6)) for m in members_shown) if members_shown else 0
        per_tw = {m: top_words(member_msgs[m], n=6) for m in members_shown}
        for i in range(max_rows_w):
            wt.add_row(*[f"{per_tw[m][i][0]} ({per_tw[m][i][1]})" if i < len(per_tw[m]) else "" for m in members_shown])
        console.print(Padding(wt, (0, 2)))
        console.print()

        # Per-member peak hour
        console.print(Rule("[section]Per-Member Peak Hour[/section]"))
        console.print()
        ph_tbl = Table(box=None, show_header=False, padding=(0, 2))
        ph_tbl.add_column(style="stat.key", min_width=18)
        ph_tbl.add_column(style="stat.val")
        for member, msgs in list(member_msgs.items())[:8]:
            h_ctr = Counter(datetime.fromtimestamp(apple_to_unix(r["date"])).hour for r in msgs)
            if h_ctr:
                ph = max(h_ctr, key=h_ctr.get)
                ph_tbl.add_row(member, f"{ph:02d}:00–{ph:02d}:59  ({h_ctr[ph]} msgs)")
        console.print(Padding(ph_tbl, (0, 2)))
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
    ts_t = Text(f"[{ts}]", style="chat.ts" if not is_ctx else "dim")
    who = Text()
    if is_me:
        who.append("  you", style="chat.me" if not is_ctx else "dim")
        who.append("  →  ", style="dim white")
    else:
        who.append(f"  {handle or 'them'}", style="chat.them" if not is_ctx else "dim white")
        who.append("  ·  ", style="dim white")
    body = Text(row["text"] or "[no text]", style="ctx.line") if is_ctx else highlight_match(row["text"] or "[no text]", query)
    console.print(Text.assemble(ts_t, " ", who, body))


def chat_label(row, do_redact, is_group=False) -> str:
    name = row["display_name"] or ""
    ident = row["chat_identifier"] or ""
    label = name if name else ident
    if not label:
        label = row["sender_handle"] or "Unknown"
    if do_redact and not name:
        label = redact(label)
    prefix = "👥 " if is_group else ""
    return prefix + label


def print_results_human(rows, conn, args, do_redact, is_group=False):
    query = args.text or ""
    ctx_n = args.context or 0
    seen_ctx: set = set()
    sort = getattr(args, "sort", "desc")
    display_rows = rows if sort == "asc" else list(reversed(rows))

    current_chat = None
    for row in display_rows:
        cid = row["chat_id"]
        if cid != current_chat:
            current_chat = cid
            console.print()
            console.print(Panel(
                f"[chat.header]{chat_label(row, do_redact, is_group=is_group)}[/chat.header]",
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
    out = []
    for row in rows:
        sender = row["sender_handle"] or ""
        ident = row["chat_identifier"] or ""
        if do_redact:
            if not row["is_from_me"]:
                sender = redact(sender)
            ident = redact(ident)
        out.append({
            "timestamp":       fmt_ts(row["date"]),
            "chat_identifier": ident,
            "chat_name":       row["display_name"] or "",
            "sender":          sender,
            "is_from_me":      bool(row["is_from_me"]),
            "text":            row["text"] or "",
        })
    print(json.dumps(out, indent=2))


def print_summary(args, count, group_name=None):
    parts = []
    if group_name:   parts.append(f"group=[bold]{group_name}[/bold]")
    if args.text:    parts.append(f"text=[bold]'{args.text}'[/bold]")
    if args.contact: parts.append(f"contact=[bold]{args.contact}[/bold]")
    if getattr(args, "member", None): parts.append(f"member=[bold]{args.member}[/bold]")
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
    # Search
    p.add_argument("--text",    "-t", metavar="QUERY")
    p.add_argument("--contact", "-c", metavar="HANDLE")
    p.add_argument("--between", "-b", nargs=2, metavar=("A", "B"))
    p.add_argument("--from",    dest="from_date", metavar="DATE")
    p.add_argument("--to",      dest="to_date",   metavar="DATE")
    p.add_argument("--context", "-x", type=int, default=0, metavar="N")
    p.add_argument("--limit",   "-l", type=int, default=50, metavar="N")
    # Group chat
    p.add_argument("--list-groups", dest="list_groups", action="store_true")
    p.add_argument("--group",   "-g", metavar="NAME")
    p.add_argument("--member",  "-m", metavar="HANDLE")
    # Stats & output
    p.add_argument("--stats",     "-s", action="store_true")
    p.add_argument("--deep",      "-d", action="store_true", help="Deeper analysis (slower)")
    p.add_argument("--reactions",       action="store_true", help="Show reaction analytics only")
    p.add_argument("--sort",      choices=["asc", "desc"], default="desc")
    p.add_argument("--json",      "-j", dest="as_json", action="store_true")
    p.add_argument("--redact",    "-r", action="store_true")
    p.add_argument("--db",        metavar="PATH", default=DEFAULT_DB)
    p.add_argument("--no-banner", dest="no_banner", action="store_true")
    p.add_argument("--version",   "-V", action="store_true")
    p.add_argument("--help",      "-h", action="store_true")
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

    conn = open_db(args.db)

    # ── List groups ──
    if args.list_groups:
        run_list_groups(conn, args.limit, args.redact)
        conn.close()
        return

    # ── Resolve group chat ──
    group_chat_id = None
    group_name = None
    if args.group:
        group_chat_id, group_name = resolve_group(conn, args.group)

    # ── Reactions standalone mode ──
    if args.reactions:
        if group_chat_id:
            rr = fetch_reactions(conn, group_chat_id=group_chat_id)
            print_reactions_group(rr, get_group_members(conn, group_chat_id), args.redact)
        elif args.contact:
            rr = fetch_reactions(conn, handle=args.contact)
            print_reactions_dm(rr, args.redact)
        else:
            err("--reactions requires --contact HANDLE or --group NAME")
        conn.close()
        return

    # ── Stats mode ──
    if args.stats:
        if group_chat_id:
            run_stats_group(conn, group_chat_id, group_name, args.redact, deep=args.deep)
        elif args.contact:
            run_stats_dm(conn, args.contact, args.redact, deep=args.deep)
        else:
            # No contact or group → personal dashboard
            run_stats_self(conn, args.redact, deep=args.deep)
        conn.close()
        return

    # ── Search mode ──
    has_filter = any([args.text, args.contact, args.between, args.from_date, args.to_date, args.group, args.member])
    if not has_filter:
        console.print(Panel(
            "[warning]At least one search filter is required.[/warning]\n\n"
            "[tip]Run [bold]imsg-search --help[/bold] to see all options.[/tip]",
            border_style="yellow", padding=(0, 2),
        ))
        console.print()
        sys.exit(1)

    if show_banner:
        console.print(Rule("[dim]searching[/dim]"))
        console.print()

    sql, params = build_search_query(args, group_chat_id=group_chat_id)
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        err(f"Query failed: {e}")

    if args.as_json:
        print_results_json(rows, args.redact, sort=args.sort)
        conn.close()
        return

    is_group = group_chat_id is not None
    print_results_human(rows, conn if args.context else None, args, args.redact, is_group=is_group)
    conn.close()
    print_summary(args, len(rows), group_name=group_name)


if __name__ == "__main__":
    main()
