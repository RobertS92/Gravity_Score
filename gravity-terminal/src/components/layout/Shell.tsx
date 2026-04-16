import { Outlet, useLocation } from 'react-router-dom'
import { useFeedSync, useTerminalBootstrap } from '../../hooks/useTerminalBootstrap'
import { AgentOutputPanel } from './AgentOutputPanel'
import { CommandBar } from './CommandBar'
import { RightPanel } from './RightPanel'
import { Sidebar } from './Sidebar'
import styles from './Shell.module.css'
import { TopBar } from './TopBar'

export function Shell() {
  useTerminalBootstrap()
  useFeedSync()
  const location = useLocation()
  const isAiTab = location.pathname === '/gravity-ai'

  return (
    <div className={styles.shell}>
      <TopBar />
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
