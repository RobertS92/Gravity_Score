import { useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useFeedSync, useTerminalBootstrap } from '../../hooks/useTerminalBootstrap'
import { mapDashboardTabToPath, usePreferencesStore } from '../../stores/preferencesStore'
import { useAlertStore } from '../../stores/alertStore'
import { AgentOutputPanel } from './AgentOutputPanel'
import { AlertStrip } from './AlertStrip'
import { CommandBar } from './CommandBar'
import { RightPanel } from './RightPanel'
import { Sidebar } from './Sidebar'
import styles from './Shell.module.css'
import { TopBar } from './TopBar'

export function Shell() {
  useTerminalBootstrap()
  useFeedSync()
  const location = useLocation()
  const navigate = useNavigate()
  const isAiTab = location.pathname === '/gravity-ai'
  const activeSports = usePreferencesStore((s) => s.activeSports)

  useEffect(() => {
    const { initialNavDone, setInitialNavDone, initialTabKey } = usePreferencesStore.getState()
    if (initialNavDone) return
    if (location.pathname !== '/') return
    const target = mapDashboardTabToPath(initialTabKey)
    if (target !== '/') {
      navigate(target, { replace: true })
    }
    setInitialNavDone()
  }, [location.pathname, navigate])

  useEffect(() => {
    void useAlertStore.getState().loadAlerts()
  }, [activeSports.join(',')])

  return (
    <div className={styles.shell}>
      <TopBar />
      <AlertStrip />
      <div className={styles.body}>
        <Sidebar />
        <main className={styles.main}>
          {!isAiTab && <AgentOutputPanel />}
          <div className={isAiTab ? styles.mainScrollAi : styles.mainScroll}>
            <Outlet />
          </div>
        </main>
        {!isAiTab && <RightPanel />}
      </div>
      {!isAiTab && <CommandBar />}
    </div>
  )
}
