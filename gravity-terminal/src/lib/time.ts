export function formatUpdatedAgo(iso: string | null | undefined): { text: string; stale: boolean } {
  if (!iso) return { text: 'UPDATED \u2014', stale: true }
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return { text: 'UPDATED \u2014', stale: true }
  const diff = Date.now() - t
  const hours = Math.floor(diff / (60 * 60 * 1000))
  const days = Math.floor(hours / 24)
  let label: string
  if (days >= 1) label = `${days}D AGO`
  else if (hours >= 1) label = `${hours}H AGO`
  else {
    const m = Math.max(1, Math.floor(diff / (60 * 1000)))
    label = `${m}M AGO`
  }
  return { text: `UPDATED ${label}`, stale: diff > 24 * 60 * 60 * 1000 }
}

export function formatFeedTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'America/New_York',
  })
}

export function etTimeString(): string {
  return new Date().toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'America/New_York',
  })
}
