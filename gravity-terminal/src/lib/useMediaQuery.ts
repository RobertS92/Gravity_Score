import { useEffect, useState } from 'react'

/**
 * React hook that subscribes to a CSS media query and re-renders whenever it
 * changes. Used to drive breakpoint-aware UI (e.g. tablet vs desktop config
 * panel layouts) without coupling layout to global state.
 *
 * SSR-safe: returns `false` on the server / before mount when `window` is
 * unavailable. The first render after mount syncs the actual state, so any
 * "off-by-one paint" only flashes once and never persists.
 */
export function useMediaQuery(query: string): boolean {
  const getMatch = () => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return false
    }
    return window.matchMedia(query).matches
  }

  const [matches, setMatches] = useState<boolean>(getMatch)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return
    }
    const mql = window.matchMedia(query)
    const handler = (event: MediaQueryListEvent) => setMatches(event.matches)
    setMatches(mql.matches)
    // `addEventListener` is the modern API; fall back to `addListener` for
    // older Safari builds. Both are torn down identically.
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', handler)
      return () => mql.removeEventListener('change', handler)
    }
    mql.addListener(handler)
    return () => mql.removeListener(handler)
  }, [query])

  return matches
}

/** Common breakpoint helpers. Keeping them centralized avoids magic strings. */
export const useIsTabletOrBelow = () => useMediaQuery('(max-width: 1024px)')
export const useIsNarrowDesktop = () => useMediaQuery('(max-width: 1280px)')
