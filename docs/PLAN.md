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
- **A clear README** covering: what it is and who it's for (Pi Zero/Zero 2 W owners who want a simple read-only wall display), a hardware list, the screenshots we already generated (great for a repo — people judge these visually), and step-by-step setup instructions — which is largely what this plan document already is, so it can mostly be adapted rather than written from nothing.
- **A LICENSE file** (something permissive like MIT is typical for a hobby project like this) so others know they're free to use and modify it.
- **A short "getting your own credentials" guide** for each source (how to get a Google/Outlook/Yahoo ICS link, how to register an Azure app for Graph API access) — again, content we've already worked out in this conversation.

**Status: repo skeleton is done.** This repo (`pi_calendar`, connected to `https://github.com/SlobodanKuzmanovic/pi_calendar`) now has: `README.md`, `LICENSE` (MIT), `.gitignore`, `requirements.txt`, `config.example.yaml`, the three `systemd/` unit files, a `screenshots/dashboard-preview.png`, and a `dashboard/main.py` placeholder with the TODO breakdown for Phase 1. None of it is committed to git yet — that's one of the open items below. What's left is entirely the real implementation (Phase 1) and later phases, not packaging.

## Open items

- [ ] Review the scaffolded repo files (README, config.example.yaml, systemd units, LICENSE) and adjust anything that doesn't match preference
- [ ] `git add` + commit + push the scaffolded files to GitHub
- [ ] Confirm the laptop monitor's native resolution (needed to size the generated image correctly, and to update `config.example.yaml`'s `display.width`/`height` — current mockups use 1366×768 as a placeholder)
- [ ] Reflash the SD card to a current Raspberry Pi OS Lite release; enable SSH + Wi-Fi via Raspberry Pi Imager
- [ ] Get the personal Microsoft account's ICS calendar link (Outlook.com → Settings → Share calendars)
- [ ] Register an Azure AD app for Microsoft Graph access (To Do), using the device-code flow (no client secret needed)
- [ ] Write the real `dashboard/main.py`: `load_config`, `fetch_calendars` (icalendar + recurring-ical-events), `fetch_todo` (msal device-code flow + Graph API), `render` (adapt the approved mockup rendering code to real data + the confirmed resolution)
- [ ] `git clone` the repo onto the Pi, `pip install -r requirements.txt`, copy `config.example.yaml` to `config.yaml` and fill in real values
- [ ] Install `fbi` (`sudo apt install fbi`), copy the `systemd/` unit files into `/etc/systemd/system/`, enable + start them
- [ ] Verify the dashboard renders correctly and survives a reboot — Phase 1 complete
- [ ] Add Google + Yahoo calendars to `config.yaml` — Phase 2 (no code change needed)
- [ ] Add work Microsoft 365 calendar — Phase 3 (where the admin-consent / ICS-policy risk gets tested)
- [ ] Decide on optional extras (weather, motion sensor, etc.) or keep it minimal — Phase 4
