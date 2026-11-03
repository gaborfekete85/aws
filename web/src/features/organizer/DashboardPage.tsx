import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import type { EventDto, EventStatus } from '../events/eventsApi'
import { formatPrice, formatWhen } from '../events/format'
import {
  apiErrorMessage,
  useCancelEventMutation,
  useListMyEventsQuery,
  usePublishEventMutation,
} from './organizerApi'

const TABS: { label: string; status?: EventStatus }[] = [
  { label: 'All' },
  { label: 'Drafts', status: 'draft' },
  { label: 'Published', status: 'published' },
  { label: 'Cancelled', status: 'cancelled' },
]

type Pending = { action: 'publish' | 'cancel'; event: EventDto } | null

export function DashboardPage() {
  const [tab, setTab] = useState(0)
  const { data, isLoading, error } = useListMyEventsQuery(TABS[tab].status)
  const [publish] = usePublishEventMutation()
  const [cancel] = useCancelEventMutation()
  const [pending, setPending] = useState<Pending>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  async function confirm() {
    if (!pending) return
    const run = pending.action === 'publish' ? publish : cancel
    setPending(null)
    const result = await run(pending.event.id)
    setActionError('error' in result ? apiErrorMessage(result.error) : null)
  }

  return (
    <section>
      <div className="row">
        <h1>My Events</h1>
        <Link to="/organizer/events/new" className="button">
          New Event
        </Link>
      </div>
      <div role="tablist" className="tabs">
        {TABS.map((t, i) => (
          <button
            key={t.label}
            role="tab"
            type="button"
            aria-selected={tab === i}
            className={tab === i ? undefined : 'secondary'}
            onClick={() => setTab(i)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {actionError && (
        <p role="alert" className="error">
          {actionError}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          Could not load your Events.
        </p>
      )}
      {isLoading && <p className="muted">Loading…</p>}
      {data && data.items.length === 0 && <p className="muted">No Events here yet.</p>}
      <table className="table">
        <tbody>
          {data?.items.map((event) => (
            <tr key={event.id}>
              <td>
                <Link to={`/organizer/events/${event.id}`}>{event.title}</Link>
                <div className="muted">{formatWhen(event.starts_at)}</div>
              </td>
              <td>
                <span className={`badge badge-${event.status}`}>{event.status}</span>
              </td>
              <td>
                {event.places} places · {formatPrice(event.price_cents, event.currency)}
              </td>
              <td className="actions">
                {event.status === 'draft' && (
                  <button type="button" onClick={() => setPending({ action: 'publish', event })}>
                    Publish
                  </button>
                )}
                {event.status === 'published' && (
                  <button type="button" className="danger" onClick={() => setPending({ action: 'cancel', event })}>
                    Cancel Event
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ConfirmDialog
        open={pending?.action === 'publish'}
        title={`Publish "${pending?.event.title ?? ''}"?`}
        confirmLabel="Publish"
        onConfirm={confirm}
        onCancel={() => setPending(null)}
      >
        It becomes visible in search and open for Booking.
      </ConfirmDialog>
      <ConfirmDialog
        open={pending?.action === 'cancel'}
        title={`Cancel "${pending?.event.title ?? ''}"?`}
        confirmLabel="Cancel Event"
        danger
        onConfirm={confirm}
        onCancel={() => setPending(null)}
      >
        All Bookings are cancelled and every Attendee is emailed. This cannot be undone.
      </ConfirmDialog>
    </section>
  )
}
