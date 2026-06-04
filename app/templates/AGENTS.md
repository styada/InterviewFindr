# AGENTS.md — `app/templates/`

## What lives here

Jinja2 HTML templates rendered by `app.api.ui`.
- `base.html` — shared layout (header, main, static assets).
- `login.html` — sign-in form (Plan 1).
- `profile.html`, `matches.html`, `match_detail.html` — added in Phase 1.

## Conventions

- All templates extend `base.html`.
- Forms use HTMX (`hx-post`, `hx-target`, `hx-swap`).
- No business logic in templates — only rendering.
- Use `class="..."` Tailwind utility classes; do not write inline `style="..."`.
