import { formatFeedTime } from '../../lib/time'
import type { FeedEventRecord } from '../../types/feed'
import { FeedTag } from '../shared/FeedTag'
import styles from './LiveFeed.module.css'

function FeedBody({ body, entity }: { body: string; entity?: string | null }) {
  if (!entity) return <>{body}</>
  const i = body.indexOf(entity)
  if (i < 0) {
    return (
      <>
        {body} <span className={styles.entity}>{entity}</span>
      </>
    )
  }
  return (
    <>
      {body.slice(0, i)}
      <span className={styles.entity}>{entity}</span>
      {body.slice(i + entity.length)}
    </>
  )
}

export function LiveFeed({
  events,
  newEventIds,
}: {
  events: FeedEventRecord[]
  newEventIds: Set<string>
}) {
  const top = events.slice(0, 10)
  return (
    <div>
      <div className={styles.label}>LIVE FEED</div>
      {top.map((e) => (
        <div
          key={e.event_id}
          className={`${styles.item} ${newEventIds.has(e.event_id) ? styles.newItem : ''}`}
        >
          <div className={styles.ts}>{formatFeedTime(e.timestamp)}</div>
          <div className={styles.body}>
            <FeedBody body={e.body} entity={e.entity_name} />
          </div>
          <FeedTag type={e.event_type} />
        </div>
      ))}
    </div>
  )
}
