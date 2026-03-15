# imsg-search Context & Guidelines

## Project Overview
`imsg-search` is a fast, safe, and beautiful command-line tool that searches local iMessage history (`chat.db`) on macOS.
- **Core principles**: No cloud, zero network, zero write risk (read-only SQLite), visually beautiful (`rich`).
- **Dependencies**: Only `rich` is allowed. The rest must be standard library Python (e.g., `sqlite3`, `argparse`, `json`).

## Recent Architectural Decisions & Fixes
- **Timezone Handling**: SQLite's `localtime` modifier is flawed for historical data. All time-bucketing (hourly peaks, monthly volumes) must be done in Python using `datetime.fromtimestamp()` mapped against `apple_to_unix()`.
- **Timestamp Formatting**: Timestamps are displayed in 12-hour AM/PM format (`%-I:%M %p`) instead of military 24-hour time.
- **JSON Output**: The `--json` flag works for searches as well as all `--stats`, `--reactions`, and `--list-groups` commands.
- **Privacy/Docs**: Screenshots in `README.md` use an image (`demo.png`) generated via HTML/CSS instead of raw `ansi` blocks to ensure compatibility on GitHub. Fictional `555` numbers are used in documentation to protect PII.

## Development Patterns
- **Database Access**: Always use `file:{PATH}?mode=ro` with `uri=True` to ensure the database can never be modified.
- **UI/UX**: Use `rich` for all terminal UI (tables, panels, sparklines). Keep the output clean, colorful, and instantly readable.
- **Filtering**: Attachment-only messages (where `text IS NULL` or empty) are excluded from text searches using `REAL_MSG_FILTER`.
- **Modularity**: Ensure that functions separating database querying from UI rendering remain clean so JSON export logic is simple.
