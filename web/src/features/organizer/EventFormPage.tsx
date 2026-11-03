import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CoverPicture } from '../events/EventCard'
import type { EventDto } from '../events/eventsApi'
import { changedFields, EMPTY, fromEvent, toInput, type FormState } from './eventForm'
import {
  apiErrorMessage,
  uploadToS3,
  useAttachCoverMutation,
  useCoverUploadUrlMutation,
  useCreateEventMutation,
  useGetMyEventQuery,
  useUpdateEventMutation,
} from './organizerApi'

const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp']
const MAX_BYTES = 5 * 1024 * 1024

function EventForm({ initial, existing }: { initial: FormState; existing?: EventDto }) {
  const navigate = useNavigate()
  const [form, setForm] = useState(initial)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [createEvent, { isLoading: creating }] = useCreateEventMutation()
  const [updateEvent, { isLoading: updating }] = useUpdateEventMutation()
  const cancelled = existing?.status === 'cancelled'

  const field =
    (name: keyof FormState) => (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm({ ...form, [name]: e.target.value })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaved(false)
    if (new Date(form.ends_at) <= new Date(form.starts_at)) {
      setError('The Event must end after it starts.')
      return
    }
    const input = toInput(form)
    if (!existing) {
      const result = await createEvent(input)
      if ('error' in result) return setError(apiErrorMessage(result.error))
      navigate(`/organizer/events/${result.data.id}`, { replace: true })
      return
    }
    const changes = changedFields(toInput(fromEvent(existing)), input)
    if (Object.keys(changes).length === 0) return setSaved(true)
    const result = await updateEvent({ id: existing.id, changes })
    if ('error' in result) return setError(apiErrorMessage(result.error))
    setSaved(true)
  }

  return (
    <form onSubmit={onSubmit} className="card" aria-label="Event details">
      <fieldset disabled={cancelled}>
        <label>
          Title
          <input required maxLength={120} value={form.title} onChange={field('title')} />
        </label>
        <label>
          Description
          <textarea rows={4} maxLength={10000} value={form.description} onChange={field('description')} />
        </label>
        <label>
          Important information
          <textarea
            rows={3}
            maxLength={2000}
            placeholder="Dress code, age limit, what to bring…"
            value={form.important_information}
            onChange={field('important_information')}
          />
        </label>
        <div className="grid-2">
          <label>
            Starts
            <input type="datetime-local" required value={form.starts_at} onChange={field('starts_at')} />
          </label>
          <label>
            Ends
            <input type="datetime-local" required value={form.ends_at} onChange={field('ends_at')} />
          </label>
          <label>
            Places
            <input type="number" min={1} max={100000} required value={form.places} onChange={field('places')} />
          </label>
          <label>
            Price per place
            <span className="inline">
              <input type="number" min={0} step="0.05" required value={form.price} onChange={field('price')} />
              <select aria-label="Currency" value={form.currency} onChange={field('currency')}>
                {['CHF', 'EUR', 'USD', 'GBP'].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </span>
          </label>
        </div>
        <h2>Location</h2>
        <label>
          Location name
          <input required value={form.location_name} onChange={field('location_name')} placeholder="Seebad Enge" />
        </label>
        <div className="grid-2">
          <label>
            Address
            <input required value={form.address} onChange={field('address')} placeholder="Mythenquai 9" />
          </label>
          <label>
            City
            <input required value={form.city} onChange={field('city')} placeholder="Zürich" />
          </label>
        </div>
      </fieldset>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {saved && <p role="status">Saved.</p>}
      {!cancelled && (
        <button type="submit" disabled={creating || updating}>
          {existing ? (updating ? 'Saving…' : 'Save changes') : creating ? 'Creating…' : 'Create draft'}
        </button>
      )}
    </form>
  )
}

function CoverUpload({ event }: { event: EventDto }) {
  const [requestUpload] = useCoverUploadUrlMutation()
  const [attach] = useAttachCoverMutation()
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setError(null)
    if (!ACCEPTED.includes(file.type)) return setError('Choose a JPEG, PNG or WebP image.')
    if (file.size > MAX_BYTES) return setError('The image must be at most 5 MB.')
    try {
      setStatus('Uploading…')
      const ticket = await requestUpload({ id: event.id, content_type: file.type, content_length: file.size }).unwrap()
      await uploadToS3(ticket, file)
      await attach({ id: event.id, key: ticket.key }).unwrap()
      setStatus('Cover picture updated.')
    } catch (err) {
      setStatus(null)
      setError(err instanceof Error ? err.message : apiErrorMessage(err))
    }
  }

  return (
    <section className="card">
      <h2>Cover picture</h2>
      <CoverPicture event={event} className="cover-large" />
      <label>
        Upload a Cover picture
        <input type="file" accept={ACCEPTED.join(',')} onChange={onFile} disabled={event.status === 'cancelled'} />
      </label>
      {status && <p role="status">{status}</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  )
}

export function EventFormPage() {
  const { eventId } = useParams()
  const { data, isLoading, error } = useGetMyEventQuery(eventId ?? '', { skip: !eventId })

  if (!eventId) {
    return (
      <section>
        <p>
          <Link to="/organizer">← My Events</Link>
        </p>
        <h1>New Event</h1>
        <EventForm initial={EMPTY} />
      </section>
    )
  }
  if (isLoading) return <p className="muted">Loading…</p>
  if (error || !data) return <p className="error">Event not found.</p>
  return (
    <section className="stack">
      <p>
        <Link to="/organizer">← My Events</Link>
      </p>
      <h1>
        {data.title} <span className={`badge badge-${data.status}`}>{data.status}</span>
      </h1>
      <CoverUpload event={data} />
      <EventForm key={data.updated_at} initial={fromEvent(data)} existing={data} />
    </section>
  )
}
