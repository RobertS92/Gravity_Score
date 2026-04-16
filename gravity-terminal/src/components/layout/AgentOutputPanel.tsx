import { useCommandStore } from '../../stores/commandStore'
import styles from './AgentOutputPanel.module.css'

export function AgentOutputPanel() {
  const lastResponse = useCommandStore((s) => s.lastResponse)
  const lastCommand = useCommandStore((s) => s.lastCommand)
  const clearLastOutput = useCommandStore((s) => s.clearLastOutput)

  if (!lastResponse?.trim()) return null

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <span>AGENT OUTPUT {lastCommand ? `· ${lastCommand}` : ''}</span>
        <button type="button" className={styles.dismiss} onClick={() => clearLastOutput()}>
          DISMISS
        </button>
      </div>
      <pre className={styles.body}>{lastResponse}</pre>
    </div>
  )
}
