#!/bin/sh
set -e
cd /app
if [ "${VITE_USE_MOCKS:-}" = "true" ]; then
  printf '%s\n' "window.__GRAVITY_API_URL__='';" > dist/env-config.js
else
  node <<'NODE'
const fs = require('fs')
const u = process.env.VITE_API_URL || ''
if (!u || !/^https?:\/\/[^/]+/.test(u)) {
  console.error(
    'ERROR: VITE_API_URL must be set at container runtime to a URL with a hostname (e.g. https://your-api.up.railway.app/v1).',
  )
  console.error('Got:', JSON.stringify(u))
  console.error(
    'If you see https:///v1, the Railway reference did not resolve: set a literal API URL on this service, or ensure Gravity_Score has a public domain first.',
  )
  process.exit(1)
}
fs.writeFileSync('dist/env-config.js', `window.__GRAVITY_API_URL__=${JSON.stringify(u)};\n`)
NODE
fi
exec "$@"
