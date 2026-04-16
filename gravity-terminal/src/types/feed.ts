export type FeedEventType = 'NIL_DEAL' | 'BRAND' | 'VELOCITY' | 'SCORE_UPDATE' | 'RISK'

export interface FeedEventRecord {
  event_id: string
  athlete_id: string
  athlete_name?: string | null
  event_type: FeedEventType
  timestamp: string
  body: string
  entity_name?: string | null
  value?: number | null
}
