# Pi Calendar

A lightweight, read-only wall dashboard for the Raspberry Pi — built for low-power boards like the Pi Zero W that can't run a full browser or an Electron-based alternative (e.g. MagicMirror²).

Shown on any HDMI display:
- **This week** — every meeting from your calendars, listed in full, nothing truncated
- **This month** — a compact overview grid, color-coded dots per calendar source
- **To-do list** — synced from Microsoft To Do

![Dashboard preview](screenshots/dashboard-preview.png)

## Why not MagicMirror² or a browser-based dashboard?

This project exists because a Raspberry Pi Zero W (single-core, 512MB RAM) can't reliably run a full Chromium/Electron session. Instead, a small Python script runs periodically, fetches your calendar and to-do data, renders a single PNG with Pillow, and a minimal framebuffer viewer (`fbi`) displays it fullscreen — no browser, no desktop environment, near-zero idle resource usage.

## Status

Early stage — see [docs/PLAN.md](docs/PLAN.md) for the full design, architecture, rollout phases, and current progress. That file is the living source of truth for this project.

## Hardware

- A Raspberry Pi — built and tested for a Pi Zero W, but anything with more RAM/cores works too (just overkill)
- Any HDMI-capable display
- Raspberry Pi OS Lite

## Setup (quick version)

1. Copy `config.example.yaml` to `config.yaml` and fill in your own calendar ICS links and Microsoft Graph app credentials. `config.yaml` is gitignored — never commit your real credentials.
2. `pip install -r requirements.txt`
3. Copy the files in `systemd/` to `/etc/systemd/system/`, then enable and start them.

Full step-by-step instructions, including how to get each calendar's ICS link and how to register the Microsoft Graph app, are in [docs/PLAN.md](docs/PLAN.md).

## License

MIT — see [LICENSE](LICENSE).
