import type { CapSport } from '../api/cap'

const ORDER: CapSport[] = ['CFB', 'NCAAB', 'NCAAW']

/** First Cap sport in `activeSports` following CFB → MBB → WBB priority; default CFB. */
export function primaryCapSportFromPrefs(activeSports: string[]): CapSport {
  for (const code of ORDER) {
    if (activeSports.includes(code)) return code
  }
  return 'CFB'
}
