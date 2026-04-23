#!/bin/sh
set -e
cd /app
if [ "${VITE_USE_MOCKS:-}" = "true" ]; then
  printf '%s\n' "window.__GRAVITY_API_URL__='';" > dist/env-config.js
else
  node <<'NODE'
const fs = require('fs')
let u = (process.env.VITE_API_URL || '').trim()
// Tolerate a copy/paste where the whole "NAME=VALUE" line was pasted into the value field.
u = u.replace(/^VITE_API_URL\s*=\s*/i, '').trim()
// Strip accidental surrounding quotes (some Railway UIs wrap pasted values in quotes).
if ((u.startsWith('"') && u.endsWith('"')) || (u.startsWith("'") && u.endsWith("'"))) {
  u = u.slice(1, -1).trim()
}
if (!u || !/^https?:\/\/[^/]+/.test(u)) {
  console.error('ERROR: VITE_API_URL must be an http(s) URL with a hostname (e.g. https://your-api.up.railway.app/v1).')
  console.error('Got:', JSON.stringify(process.env.VITE_API_URL || ''))
  console.error('After cleanup:', JSON.stringify(u))
  console.error('Fix: on this service, set VITE_API_URL to just the URL. If it looks like https:///v1, the')
  console.error('${{SERVICE.RAILWAY_PUBLIC_DOMAIN}} reference did not resolve — ensure the API service has a public domain and the name matches exactly, or paste a literal https URL.')
  process.exit(1)
}
fs.writeFileSync('dist/env-config.js', `window.__GRAVITY_API_URL__=${JSON.stringify(u)};\n`)
console.log('Wrote dist/env-config.js with VITE_API_URL =', u)
NODE
fi
exec "$@"
