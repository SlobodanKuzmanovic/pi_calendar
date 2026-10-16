"""
Pi Calendar - main entry point.

Run on a schedule (see systemd/dashboard-render.timer). Each run should:
  1. Load config.yaml
  2. Fetch each calendar feed (ICS) and the Microsoft To Do list
  3. Render a single PNG (dark theme: this-week row + month grid + to-do sidebar)
  4. Save it to dashboard/current.png for the display service to show

Not implemented yet - this is a placeholder for Phase 1.
See docs/PLAN.md for the full architecture and rollout plan.

TODO:
  - [ ] load_config() -> dict
  - [ ] fetch_calendars(config) -> list[Event]      # icalendar + recurring-ical-events
  - [ ] fetch_todo(config) -> list[Task]             # msal device-code flow + Graph API
  - [ ] render(events, tasks, config) -> PIL.Image   # adapt the approved mockup rendering code
  - [ ] main(): tie it together, save to dashboard/current.png
"""


def main():
    raise NotImplementedError("Dashboard script not yet implemented - see docs/PLAN.md Phase 1")


if __name__ == "__main__":
    main()
