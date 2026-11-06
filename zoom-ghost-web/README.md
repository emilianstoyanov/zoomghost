# zoom-ghost-web

Static frontend for ZoomGhost. Netlify hosts this directory as-is. There is no build step and no backend in this folder.

How the site fits the rest of the system is documented in [../docs/architecture.md](../docs/architecture.md). Local run steps are in [../docs/getting-started.md](../docs/getting-started.md).

## What the site does

- Landing page and signed-in dashboard in `index.html`.
- Magic-link sign-in through Supabase Auth.
- Connect and disconnect Slack and Zoom.
- A list of the user's Zoom recordings.
- A support form in `chat-widget.js` that inserts into `support_messages`.
- A project page in `project-details.html`.

`app.js` switches between the landing view and the dashboard when a Supabase session exists. Tabs in the same browser share sign-out through a `BroadcastChannel` named `auth`. The session storage key is `zoom-ghost-auth`.

## Magic link

`handleMagicLinkLogin` calls `supabase.auth.signInWithOtp` with `flowType: "pkce"` and `emailRedirectTo` set to `window.location.origin`. Supabase must allow that origin.

On session setup the site upserts `users` with the user id and email, then reads active `oauth_tokens` rows for Slack and Zoom.

## Connecting accounts

Slack opens:

```text
GET {API_BASE_URL}/api/slack/install?uid={user id}
```

Zoom opens:

```text
GET {API_BASE_URL}/api/zoom/install?uid={user id}
```

Both open in a new tab. Heroku finishes OAuth and sends the browser to `FRONTEND_URL`. Disconnect sets `oauth_tokens.is_active` to false for that provider. The site does not delete the row.

The recording list calls:

```text
GET {API_BASE_URL}/api/recordings?user_id={user id}
Authorization: Bearer {supabase access token}
apikey: {anon key}
```

Each row shows the topic, the start time, and the first file's `download_url`.

## Files

| File | Role |
| --- | --- |
| `index.html` | Landing page, auth modal, dashboard |
| `project-details.html` | Project page |
| `app.js` | Session, OAuth links, recordings, toasts |
| `supabaseClient.js` | Supabase browser client |
| `chat-widget.js` | Support form |
| `style.css` | Styles |
| `assets/logo.png` | Logo and favicon |
| `config.example.js` | Template for `config.js` |

`index.html` loads Tailwind and the Supabase browser library from CDNs, then `config.js`, then `supabaseClient.js`.

## Configuration

Copy `config.example.js` to `config.js`. The site reads `window.ZOOMGHOST_CONFIG` and does not read `.env`.

```javascript
window.ZOOMGHOST_CONFIG = {
  SUPABASE_URL: "https://YOUR_PROJECT_REF.supabase.co",
  SUPABASE_ANON_KEY: "YOUR_SUPABASE_ANON_KEY",
  API_BASE_URL: "https://YOUR_SLACK_BOT_HOST"
};
```

`config.js` is gitignored. Variable details are in [../docs/configuration.md](../docs/configuration.md).

## Local development

From this directory:

```bash
python -m http.server 3000
```

Open `http://localhost:3000`. The Heroku API allows that origin when `APP_ENV` is not `production` and `CORS_ORIGINS` is unset. Set `API_BASE_URL` to the API origin, with no trailing path. `app.js` strips a trailing slash if one is present.

## Deploy

Publish this directory on Netlify and add `config.js` at deploy time. See [../docs/deployment.md](../docs/deployment.md).
