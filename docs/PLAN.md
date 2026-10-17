# Raspberry Pi Wall Dashboard — Project Plan

*This is the canonical, continuously-updated copy of the project plan, now living in this repo. (It previously lived at `C:\D\raspberry_pi\pi-dashboard-plan.md` on the project owner's machine — that copy can be deleted or kept as a backup; this one is what's kept current going forward.)*

*Not a two-way-mirror build — a read-only, always-on info screen (this week's meetings, a month overview, and a to-do list) shown on a repurposed laptop monitor via HDMI. Confirmed view-only — no touch/interaction needed on the display itself; the to-do list and calendars are still managed from your phone/laptop apps as usual.*

## Decisions so far

| Area | Decision |
|---|---|
| Hardware | **Raspberry Pi Zero W, Rev 1.1** — single-core ARM11, 512MB RAM (~429MB usable) |
| OS | Raspbian 11 (bullseye) currently on the SD card — to be reflashed to current **Raspberry Pi OS Lite** (no desktop needed) |
| Display | Old laptop monitor, HDMI into the Pi (already connected). Native resolution still unconfirmed — mockups below use 1366×768 as a placeholder |
| Software approach | **Custom Python dashboard** (MagicMirror² dropped — too heavy for a single-core/512MB board). See architecture below |
| Calendars | Google, Microsoft (personal **and** work accounts), Yahoo — all pulled in as ICS feeds |
| To-do list | **Microsoft To Do**, via Microsoft Graph API |
| Rollout order | **Starting with Microsoft To Do + personal-email calendar only.** Google, Yahoo, and the work calendar are added in later phases once the first pass is working. (Earlier plan was to do the work calendar first — reversed in favor of starting with lower-risk personal accounts.) |
| Company IT | User has decided **not** to involve their company's IT and is proceeding independently, whenever the work calendar phase is reached |
| Visual design | **Dark theme**, finalized layout: this-week row + compact month grid + to-do sidebar (see Design section) |
| Pi 4/5 upgrade | Looked into pricing (Pi 4/5 now $65-80+ for just 2GB due to 2026 memory cost hikes) — **too expensive, staying on the existing Zero W** |
| Publishing | Considering open-sourcing this as a public GitHub template project others can clone and configure with their own accounts — see new section below |

## Hardware details (confirmed from terminal output, 2026-10-15)

- Model: Raspberry Pi Zero W, Rev 1.1 (single-core — `nproc` returned `1`)
- RAM: ~429MB usable, 99MB swap configured
- Storage: 15GB SD card, only 3.2GB used, 11GB free — plenty of room
- Current OS: Raspbian GNU/Linux 11 (bullseye) — an older image; plan is to reflash to a current Raspberry Pi OS Lite release before building, for Node/package currency (even though we're not using Node now, a current OS avoids other stale-package headaches)

Because it's single-core with 512MB RAM, a browser/Electron-based approach (MagicMirror², a kiosk browser, etc.) isn't realistic — a single ARM11 core struggles to paint a full browser reliably. That's why we pivoted to a custom lightweight renderer instead.

## Custom dashboard architecture

Designed specifically for this hardware — the expensive work (network calls, image rendering) happens only once every few minutes; the rest of the time the screen just holds a static image, keeping steady-state CPU/RAM usage close to zero.

1. **A Python script, run every N minutes (e.g. every 5) via a systemd timer:**
   - Fetches each calendar feed (Google, Microsoft personal, Microsoft work, Yahoo — all `.ics` URLs) using the `icalendar` + `recurring-ical-events` libraries (handles recurring events correctly).
   - Fetches Microsoft To Do tasks via the Microsoft Graph API, authenticated with `msal` using the **device code flow** (one-time login, then tokens refresh automatically in the background).
   - Renders everything into a single image using **Pillow** (PIL) — full control over layout, fonts, colors.
   - Saves the image to a fixed path, e.g. `/home/pi/dashboard/current.png`.
2. **A minimal always-on display process** shows that image fullscreen directly on the console framebuffer using `fbi` — no X server, no browser, negligible resource usage.

**Known risk on the work account (deferred to a later phase, user's informed choice to proceed without IT when that phase arrives):** some Microsoft 365 tenants disable user consent for apps entirely, which would make the Graph API device-code login fail outright with an "admin consent required" error, independent of anything in our control. If hit, the fallback is the same ICS-feed approach already planned for the other calendars — i.e., publish the work calendar as an ICS link instead of going through Graph API for it (assuming the tenant allows calendar publishing, which is a separate setting that may or may not be enabled). Since the personal Microsoft account is what's being used for To Do + the first calendar, this risk doesn't block getting started at all.

## Visual design (finalized — dark theme)

Mockups were iterated and approved. Final layout:

- **Header**: current time + date, top right.
- **"This week" row** (top): 7 day-columns (today → +6 days), today's column boxed in a bright blue outline. Each column lists **every** meeting that day in full — time, title, and a color-coded bar per calendar source (Google = blue, Yahoo = purple, MS Work = orange, MS Personal = teal). On an unusually packed day, overflow collapses to a "+N more" line rather than breaking the layout — nothing is silently hidden, just summarized.
- **Month grid** (below, compact): the full current month as a classic grid, today boxed in blue, each day showing just its date number plus small colored dots (one per source with an event that day) — a quick-glance overview rather than full detail, since the current week's detail already lives in the row above.
- **To-do sidebar** (right, full height): Microsoft To Do items as a checklist — checked items shown dimmed/struck.
- **Dark palette**: near-black background, light text, the same source accent colors as above, which read clearly on both the light and dark versions we tested.

Still to do visually: re-render at the real monitor resolution once confirmed (currently built at a 1366×768 placeholder).

## Rollout plan (phased)

1. **Phase 1 (first working version):** Microsoft To Do (personal account) + personal-email calendar only. Gets the core script, rendering, and display service working end-to-end on real data with the lowest-friction accounts.
2. **Phase 2:** add Google and Yahoo calendars (more ICS URLs, no new code needed — the calendar-fetch logic is already multi-feed by design).
3. **Phase 3:** add the work Microsoft 365 calendar, at which point the "admin consent" / ICS-publishing-policy risk noted above actually gets tested.
4. **Phase 4 (optional):** weather, motion sensor, or other extras, if still wanted once the core is running smoothly.

## Open-sourcing on GitHub

Publishing this as a public template repo — so someone else could clone it, swap in their own calendar URLs/API keys, and run it on their own Pi — is a reasonable and genuinely useful project; there isn't much out there specifically aimed at Pi Zero-class hardware (most "Pi dashboard" projects on GitHub assume a Pi 4+ and a browser). To make it cleanly reusable rather than just "my personal script," it needs:

- **Secrets kept out of the repo entirely:** a `config.example.yaml` checked into git with placeholder values and comments, and the real `config.yaml` (with actual ICS URLs, Azure client ID, tokens) listed in `.gitignore` so it's never committed. Same for any cached OAuth token file.
- **A `requirements.txt`** pinning the Python libraries used (`Pillow`, `icalendar`, `recurring-ical-events`, `msal`, `requests`) so `pip install -r requirements.txt` just works for anyone.
- **The systemd unit files included in the repo** (the fetch/render timer + the `fbi` display service), with instructions to copy them into `/etc/systemd/system/` and enable them — rather than expecting someone to write those from scratch.
- [x] **A clear README** — `README.md` now has the full setup guide: hardware list, flashing the SD card, getting each calendar's ICS link, registering the Azure app for Microsoft To Do, configuring `config.yaml`, installing and enabling the systemd services, and a troubleshooting section covering the gotchas hit during this build (username paths, the `fbi`/systemd restart-loop fix, console blanking, getty@tty1, root-vs-user pip installs).
- [x] **A LICENSE file** — MIT, see `LICENSE`.
- [x] **A "getting your own credentials" guide** — folded into `README.md` steps 2 and 3 rather than a separate doc.

**Status: Phase 1 complete and confirmed working on the physical display.** This repo (`pi_calendar`, connected to `https://github.com/SlobodanKuzmanovic/pi_calendar`) now has: `README.md`, `LICENSE` (MIT), `.gitignore`, `requirements.txt` (Pillow, icalendar, recurring-ical-events, msal, requests, PyYAML), `config.example.yaml`, the three `systemd/` unit files, `screenshots/dashboard-preview.png`, and a working `dashboard/main.py` (load_config, fetch_calendars, fetch_todo, render, main — tested locally, degrades gracefully with no config/credentials). The dark-theme WorkSans fonts used by the approved mockup are bundled at `dashboard/fonts/` so the script doesn't depend on fonts being present on the Pi. SD card is reflashed with Raspberry Pi OS Lite (32-bit), SSH + Wi-Fi configured. Microsoft account setup (personal ICS link + Azure app registration, device-code flow, Tasks.ReadWrite) is complete — both the ICS URL and the Application (client) ID are collected and ready to go into `config.yaml` on the Pi.

What's left is entirely the on-Pi setup and first real run (Phase 1), not more code or scaffolding.

## Open items

- [x] Review the scaffolded repo files
- [x] `git add` + commit + push the scaffolded files to GitHub
- [x] Confirm the laptop monitor's native resolution — 1920×1080, already set in `config.example.yaml`
- [x] Reflash the SD card to Raspberry Pi OS Lite (32-bit); SSH + Wi-Fi enabled via Raspberry Pi Imager
- [x] Get the personal Microsoft account's ICS calendar link (Outlook.com → Settings → Shared calendars → Publish a calendar)
- [x] Register an Azure app for Microsoft Graph access (To Do): "Personal Microsoft accounts", Allow public client flows: Enabled, Tasks.ReadWrite delegated permission added, Application (client) ID collected
- [x] Write the real `dashboard/main.py` — implemented and tested locally (renders correctly with and without real data)
- [x] SSH into the Pi; `git clone https://github.com/SlobodanKuzmanovic/pi_calendar.git`, `cd pi_calendar`
- [x] `sudo apt update && sudo apt install -y python3-pip fbi`
- [x] `sudo pip3 install -r requirements.txt --break-system-packages` (must be system-wide/sudo — the display/render services run as root and won't see packages installed into a regular user's own site-packages)
- [x] `cp config.example.yaml config.yaml` and fill in the real ICS URL and Azure client ID
- [x] Run `python3 dashboard/main.py` manually once, complete the one-time device-code sign-in, confirm `dashboard/current.png` is created and looks right
- [x] Copy the `systemd/` unit files into `/etc/systemd/system/`, `sudo systemctl daemon-reload`, enable + start `dashboard-render.timer` and `dashboard-display.service`
- [x] `sudo systemctl disable --now getty@tty1.service` (the default login prompt on tty1 fights `fbi` for the console)
- [x] Verify the dashboard renders correctly on the actual monitor — Phase 1 complete

### Pi deployment gotchas hit (now fixed in the repo's systemd files and docs)

- systemd unit files originally assumed username "pi" — updated to the actual username "calendar" once the Pi was set up. Anyone using a different username needs to edit the paths in `systemd/*.service`.
- `fbi` run under systemd exits almost immediately without a real controlling terminal attached, and with `Restart=always` this crash-loops and corrupts the framebuffer (symptom: screen shows nothing or goes solid black after many restarts). Fixed by giving the service `StandardInput=tty` / `StandardOutput=tty` / `TTYPath=/dev/tty1`, and — since `fbi` can still exit shortly after drawing the image even with those set — wrapping `ExecStart` as `fbi ...; exec tail -f /dev/null` so the service stays "running" (and systemd stops restarting it) once the image is on screen.
- Raspberry Pi OS's console idle screen-blanking can blank tty1 regardless of what's on it. If the screen goes black after a while even with the display service stable, disable it: `sudo raspi-config nonint do_blanking 1` and/or add `consoleblank=0` to `/boot/cmdline.txt`.
- `pip install --break-system-packages` without `sudo` installs to the invoking user's own site-packages, invisible to the systemd services which run as root — install with `sudo pip3 install ...` instead.
- [ ] Add Google + Yahoo calendars to `config.yaml` — Phase 2 (no code change needed)
- [ ] Add work Microsoft 365 calendar — Phase 3 (where the admin-consent / ICS-policy risk gets tested)
- [ ] Decide on optional extras (weather, motion sensor, etc.) or keep it minimal — Phase 4
