<p align="center">
  <img src="logo.png" alt="imsg-search" width="600" />
</p>

<p align="center">
  <strong>Search your iMessages from the terminal. Instantly.</strong><br/>
  Full-text search · contact lookup · group chats · conversation analytics · JSON pipeline output
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/platform-macOS-lightgrey?style=flat-square&logo=apple" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" />
  <img src="https://img.shields.io/badge/read--only-safe-brightgreen?style=flat-square" />
  <img src="https://img.shields.io/badge/PRs-welcome-blueviolet?style=flat-square" />
</p>

---

## What is this?

`imsg-search` is a fast, safe, beautiful command-line tool that searches your local iMessage history — the SQLite database macOS keeps right on your machine.

No cloud. No API keys. No sending your messages anywhere.  
Just you, your terminal, and 10+ years of chat history at your fingertips.

<p align="center">
  <img src="demo.png" alt="imsg-search demo" width="720" />
</p>

---

## Features

- 🔍 **Full-text search** — find any word or phrase across all your messages instantly
- 👤 **Contact filter** — scope search to a specific phone number or Apple ID
- 👥 **Group chat support** — search within group chats, filter by member, list all groups
- 🔗 **Between filter** — find chats where two specific contacts both appear
- 📅 **Date ranges** — `--from` / `--to` with YYYY-MM-DD syntax
- 💬 **Context mode** — show N messages before and after each match (like `grep -C`)
- 📱 **Personal stats** — your own iMessage overview: top contacts, top groups, monthly sparkline
- 📊 **Contact & group stats** — deep analytics with activity heatmaps, top words, per-member breakdowns
- ❤️  **Reaction analytics** — who reacts to what, per-contact and per-member reactor tables
- 🔎 **Deep mode** — `--deep` for per-member word counts, peak hours, and more thorough analysis
- 🔒 **Redact mode** — mask all phone numbers for safe screenshots and logs
- 📡 **JSON output** — machine-readable output for pipelines and dashboards
- 🛡️ **Read-only & safe** — opens `chat.db` in read-only mode, parameterized SQL, zero write risk
- 🎨 **Beautiful output** — colored panels, highlighted matches, sparklines, emoji reaction charts

---

## Requirements

- macOS (iMessage stores chats locally in `~/Library/Messages/chat.db`)
- Python 3.9+
- [Full Disk Access](https://support.apple.com/guide/mac-help/mchld6aa7d23/mac) for Terminal (System Settings → Privacy & Security → Full Disk Access)

---

## Install

```bash
# 1. Clone the repo
git clone https://github.com/dustindog101/imsg-search.git
cd imsg-search

# 2. Install the one dependency
pip install rich

# 3. (Optional) Make it available system-wide
chmod +x imsg_search.py
sudo ln -s "$(pwd)/imsg_search.py" /usr/local/bin/imsg-search
```

---

## Usage

```
imsg-search [OPTIONS]

All filters are optional and fully composable.
```

### Options

| Flag               | Shorthand | Argument    | Description                                                                    |
| ------------------ | --------- | ----------- | ------------------------------------------------------------------------------ |
| `--text`           | `-t`      | `QUERY`     | Search message text (case-insensitive)                                         |
| `--contact`        | `-c`      | `HANDLE`    | Filter by phone number or Apple ID (DMs)                                       |
| `--between`        | `-b`      | `A B`       | Chats where BOTH handles appear                                                |
| `--from`           |           | `DATE`      | Start date, inclusive (YYYY-MM-DD)                                             |
| `--to`             |           | `DATE`      | End date, inclusive (YYYY-MM-DD)                                               |
| `--context`        | `-x`      | `N`         | Show N messages around each match                                              |
| `--limit`          | `-l`      | `N`         | Max results (default: 50)                                                      |
| `--sort`           |           | `asc\|desc` | `asc`=oldest first, `desc`=newest first (default)                              |
|                    |           |             |                                                                                |
| **Group Chat**     |           |             |                                                                                |
| `--list-groups`    |           |             | List all group chats (ranked by activity)                                      |
| `--group`          | `-g`      | `NAME`      | Search within a group chat (name or chat ID)                                   |
| `--member`         | `-m`      | `HANDLE`    | Filter to a participant within a group                                         |
|                    |           |             |                                                                                |
| **Stats & Output** |           |             |                                                                                |
| `--stats`          | `-s`      |             | Analytics: alone=personal overview, with `--contact`/`--group`=targeted        |
| `--deep`           | `-d`      |             | Deeper analysis for `--stats` (per-member words, peak hours, global top words) |
| `--reactions`      |           |             | Standalone reaction report for a contact or group                              |
| `--json`           | `-j`      |             | Machine-readable JSON output                                                   |
| `--redact`         | `-r`      |             | Mask phone numbers in output                                                   |
| `--db`             |           | `PATH`      | Custom path to chat.db                                                         |
| `--no-banner`      |           |             | Suppress startup banner                                                        |
| `--version`        | `-V`      |             | Print version                                                                  |
| `--help`           | `-h`      |             | Show help page                                                                 |

---

## Examples

### Search by keyword

```bash
imsg-search --text "fleet street"
```

### Filter to a specific contact

```bash
imsg-search --contact +12025551234
```

### Keyword + contact + date range

```bash
imsg-search --text "lunch" --contact +12025551234 --from 2024-01-01 --to 2024-12-31
```

### Context around matches

Show 3 messages before and after each hit — like `grep -C 3`:

```bash
imsg-search --text "hey" --context 3
```

### Find chats involving two specific people

```bash
imsg-search --between +12025551234 +19175550000
```

### Your personal stats dashboard

No contact or group needed — just `--stats` alone:

```bash
imsg-search --stats            # fast: totals, top contacts, top groups, sparkline
imsg-search --stats --deep     # adds your most-used words and busiest hour globally
```

```
╭──────────────────────────────╮
│  📱  Your iMessage Overview  │
╰──────────────────────────────╯

  Total messages   142,301    DM conversations  2,395
  Group chats          392    Messaging since   2019-09-04

── Top Contacts ──────────────────────────────────────────
  +13015550142   █████████████████████████ 42,320
  +12025550156   ████████                   8,241
  +12405550144   ████                       3,101

── Top Groups ────────────────────────────────────────────
  Weekend Warriors 2026 (13👥)   ████████████████  24,001
  Family (5👥)                   ███                1,848

── Monthly Volume ────────────────────────────────────────
  ▁▂▃▄▅▆▇█▇▆▅▄▃▄▅▆▇█
  2019-09                                      2026-03
```

### Deep contact analytics

```bash
imsg-search --contact +12025551234 --stats
```

```
╭──────────────────╮
│  +12025551234    │
╰──────────────────╯

  Total messages    1,204      First message  2022-09-25 16:12
  You sent          612 (51%)  Last message   2024-11-14 23:07
  They sent         592 (49%)  Relationship   777 days

── Top Words ────────────────────────────────────────────
  Your top words          Their top words
  bro (312)               lmao (201)
  real (198)              facts (187)
  bet (155)               word (143)

── Reactions ────────────────────────────────────────────
  Their reactions to you      Your reactions to them
  ❤️  Loved    ███████  201   ❤️  Loved   ████  108
  😂  Laughed   ██      44   👍  Liked         18
```

### Reaction analytics

Standalone reaction report for any contact or group:

```bash
imsg-search --contact +12025551234 --reactions
imsg-search --group "Warriors" --reactions
```

Group reactor table shows who reacts most and with what emoji across all members.

### Deep group analytics

```bash
imsg-search --group "Warriors" --stats --deep
```

`--deep` adds per-member top words side-by-side and per-member peak hour — who's the night owl, who goes quiet on weekends.

### JSON output (for piping into dashboards)

```bash
imsg-search --text "pickup" --from 2024-01-01 --json
```

```json
[
  {
    "timestamp": "2024-03-14 18:42",
    "chat_identifier": "+12025551234",
    "chat_name": "",
    "sender": "+12025551234",
    "is_from_me": false,
    "text": "can you pickup the car"
  }
]
```

### Redact phone numbers (safe for sharing)

```bash
imsg-search --text "address" --redact
```

---

## Group Chats

`imsg-search` has first-class support for group chats — search within them, see who said what, and get per-member analytics.

### Discover your groups

```bash
imsg-search --list-groups
```

```
  👥 Group Chats
  ╭───┬────────────────────────┬─────────┬──────────┬───────────────────╮
  │ # │ Name                   │ Members │ Messages │ Last Active       │
  ├───┼────────────────────────┼─────────┼──────────┼───────────────────┤
  │ 1 │ Weekend Warriors 2026  │ 13      │ 24,001   │ 2026-03-14 21:43  │
  │ 2 │ Cabin Trip Council     │ 5       │ 1,204    │ 2026-03-12 13:15  │
  │ 3 │ (unnamed)              │ 3       │ 342      │ 2026-02-28 04:01  │
  ╰───┴────────────────────────┴─────────┴──────────┴───────────────────╯
```

### Search within a group

```bash
# By group name (partial, case-insensitive)
imsg-search --group "warriors" --text "tomorrow"

# By exact chat identifier
imsg-search --group chat381722023746962215 --text "tomorrow"
```

### Filter by a specific member

```bash
# What did a specific person say in a group?
imsg-search --group "warriors" --member +12025551234

# Combine with text search and date range
imsg-search --group "warriors" --member +12025551234 --text "dinner" --from 2025-01-01
```

### Group stats

Per-member analytics with message distribution, activity heatmap, and top words:

```bash
imsg-search --group "warriors" --stats
```

```
╭─────────────────────────────────────────────╮
│  👥  Weekend Warriors 2026  (13 members)   │
╰─────────────────────────────────────────────╯

  Total messages  24,001     First message  2025-08-14 19:12
  Members         13         Last message   2026-03-14 21:43
  Avg msgs/day    112.0      Active for     214 days

── Message Distribution ─────────────────────────────────
  +12405550144  █████████████████████████ 5,201  (22%)
  you           ████████████████████     4,010  (17%)
  +12405550191  ████████████████         3,402  (14%)
  +13015550124  ████████████             2,601  (11%)
  ...

── Hourly Activity ──────────────────────────────────────
  Peak hour  12:00–12:59  (2,154 messages)
  ▂▂▁      ▁▆▇█▆▅▅▅▆▃▆▄▃▅▄
  00                   12                   23

── Top Words (group-wide) ───────────────────────────────
  bro (1,350)  bet (861)  shi (843)  sum (677)  ima (660)
```

## Use as a data ingest

`imsg-search` outputs clean JSON, making it trivial to integrate into larger pipelines:

```bash
# Pipe today's messages into a daily digest script
imsg-search --from 2024-11-14 --json | python3 daily_digest.py

# Save to a file for later processing
imsg-search --contact +12025551234 --json > contact_export.json

# Filter through jq
imsg-search --text "meeting" --json | jq '[.[] | select(.is_from_me == false)]'
```

---

## How it works

iMessage on macOS stores your entire message history in a local SQLite database at:

```
~/Library/Messages/chat.db
```

`imsg-search` opens this database in **read-only mode** and runs parameterized SQL queries against it. No messages are sent anywhere, no accounts needed, no internet required.

Key tables used:
- `message` — every message ever sent/received
- `handle` — contact identifiers (phone numbers, Apple IDs)
- `chat` — conversation threads (`style=43` for groups, `style=45` for DMs)
- `chat_message_join` — links messages to their conversation
- `chat_handle_join` — links group chats to their participants

---

## Safety

| Property              | Detail                                                                      |
| --------------------- | --------------------------------------------------------------------------- |
| **Read-only**         | Opens `chat.db` with SQLite's `?mode=ro` URI flag — physically cannot write |
| **Parameterized SQL** | All user input goes through `?` placeholders — zero injection risk          |
| **No network**        | Runs 100% locally, no data leaves your machine                              |
| **No writes**         | Strictly `SELECT` queries only                                              |
| **Redact mode**       | `--redact` masks all phone numbers in output                                |

The only permission required is **Full Disk Access** for Terminal, which macOS requires for any app reading `chat.db`.

---

## Contributing

PRs are welcome! Some ideas:

- [x] ~~Group chat support~~ ✅ shipped in v1.1.0
- [x] ~~Reaction analytics~~ ✅ shipped in v1.2.0
- [x] ~~Personal stats dashboard~~ ✅ shipped in v1.2.0
- [x] ~~Deep mode (`--deep`)~~ ✅ shipped in v1.2.0
- [ ] Attachment search (images, files)
- [ ] Export to Markdown / HTML
- [ ] `--watch` mode for live incoming messages
- [ ] Contact name resolution (map numbers to names from Contacts.app)

### Development setup

```bash
git clone https://github.com/dustindog101/imsg-search.git
cd imsg-search
pip install rich
python3 imsg_search.py --help
```

---

## License

MIT — see [LICENSE](LICENSE)

---

<p align="center">
  Built with ❤️ for developers who live in the terminal
</p>
