# AGENTS.md — `app/static/`

## What lives here

Static assets served at `/static/`:
- `css/tailwind.css` — built Tailwind output (regenerated with the standalone CLI).
- `js/htmx.min.js` — vendored HTMX 2.0.3.
- `js/alpine.min.js` — vendored Alpine.js 3.14.3.

## Conventions

- The htmx and alpine bundles are whitelisted in `.gitignore` and committed so the app works without a CDN.
- `tailwind.css` is the build output. Until the standalone CLI is wired up, the file is a stub; production builds will overwrite it.
- Do not add NPM dependencies; this is a CDN-free deployment.
