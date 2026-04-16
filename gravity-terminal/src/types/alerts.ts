export type AlertType = 'SCORE_MOVE' | 'NIL_SIGNAL' | 'RISK_FLAG' | 'DEAL_DETECTED'
export type AlertSeverity = 'INFO' | 'WARN' | 'CRITICAL'

export interface AlertRecord {
  alert_id: string
  athlete_id: string
  athlete_name: string
  school?: string | null
  alert_type: AlertType
  severity: AlertSeverity
  description: string
  numeric_change?: number | null
  timestamp: string
}
