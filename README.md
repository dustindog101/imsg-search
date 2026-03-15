<p align="center">
  <img src="logo.png" alt="imsg-search" width="600" />
</p>

<p align="center">
  <strong>Search your iMessages from the terminal. Instantly.</strong><br/>
  Full-text search · contact lookup · conversation analytics · JSON pipeline output
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

```
$ imsg-search --text "fleet street" --context 2

╭─────────────────╮
│  +12026434356   │
╰─────────────────╯
  [2025-07-18 04:34]   you  →  I'm by Fleet Street rn
  [2025-07-18 04:42]   you  →  By Fleet Street in my car
  [2025-07-18 04:54]   +12026434356  ·  He's on fleet street by the school
  ╌╌╌

╭─────────────────────────────────────────────╮
│  6 results  ·  text='fleet street'          │
╰─────────────────────────────────────────────╯
```

---

## Features

- 🔍 **Full-text search** — find any word or phrase across all your messages instantly
- 👤 **Contact filter** — scope search to a specific phone number or Apple ID
- 🔗 **Between filter** — find chats where two specific contacts both appear
- 📅 **Date ranges** — `--from` / `--to` with YYYY-MM-DD syntax
- 💬 **Context mode** — show N messages before and after each match (like `grep -C`)
- 📊 **Stats mode** — deep analytics for any contact: message counts, activity heatmap, top words, monthly volume sparkline
- 🔒 **Redact mode** — mask all phone numbers for safe screenshots and logs
- 📡 **JSON output** — machine-readable output, perfect for piping into dashboards or scripts
- 🛡️ **Read-only & safe** — opens `chat.db` in read-only mode, parameterized SQL, zero write risk
- 🎨 **Beautiful output** — colored chat panels, highlighted matches, sparkline charts

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

| Flag          | Shorthand | Argument    | Description                                       |
| ------------- | --------- | ----------- | ------------------------------------------------- |
| `--text`      | `-t`      | `QUERY`     | Search message text (case-insensitive)            |
| `--contact`   | `-c`      | `HANDLE`    | Filter by phone number or Apple ID                |
| `--between`   | `-b`      | `A B`       | Chats where BOTH handles appear                   |
| `--from`      |           | `DATE`      | Start date, inclusive (YYYY-MM-DD)                |
| `--to`        |           | `DATE`      | End date, inclusive (YYYY-MM-DD)                  |
| `--context`   | `-x`      | `N`         | Show N messages around each match                 |
| `--limit`     | `-l`      | `N`         | Max results (default: 50)                         |
| `--sort`      |           | `asc\|desc` | `asc`=oldest first, `desc`=newest first (default) |
| `--stats`     | `-s`      |             | Deep analytics for `--contact`                    |
| `--json`      | `-j`      |             | Machine-readable JSON output                      |
| `--redact`    | `-r`      |             | Mask phone numbers in output                      |
| `--db`        |           | `PATH`      | Custom path to chat.db                            |
| `--no-banner` |           |             | Suppress startup banner                           |
| `--version`   | `-V`      |             | Print version                                     |
| `--help`      | `-h`      |             | Show help page                                    |

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

── Activity by Day ──────────────────────────────────────
  Day   You                    Them
  Mon   ████████████████ 98    █████████████ 78
  Tue   █████████████ 82       ████████████████ 94
  ...

── Hourly Activity ──────────────────────────────────────
  Peak hour  22:00–22:59  (187 messages)
  ▁▁▁▁▁▁▁▂▃▃▄▄▅▆▇█▇▆▅▄▃▂▂▁
  00                   12                   23

── Top Words ────────────────────────────────────────────
  Your top words          Their top words
  ─────────────────────────────────────────
  bro (312)               lmao (201)
  real (198)              facts (187)
  bet (155)               word (143)
```

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
- `chat` — conversation threads
- `chat_message_join` — links messages to their conversation

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

- [ ] Group chat support (named chats)
- [ ] Attachment search (images, files)
- [ ] Export to Markdown / HTML
- [ ] `--watch` mode for live incoming messages
- [ ] Integration with `imsg` CLI for sending replies

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
