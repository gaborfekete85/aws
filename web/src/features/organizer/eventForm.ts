import type { EventDto } from '../events/eventsApi'
import type { EventInput } from './organizerApi'

export interface FormState {
  title: string
  description: string
  important_information: string
  starts_at: string // datetime-local, the Organizer's local time
  ends_at: string
  places: string
  price: string // decimal, e.g. "25.00"
  currency: string
  location_name: string
  address: string
  city: string
}

const pad = (n: number) => String(n).padStart(2, '0')

/** ISO instant -> value for <input type="datetime-local"> in local time. */
export function toLocalInput(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** datetime-local value -> timezone-aware ISO string (the API rejects naive datetimes). */
export function fromLocalInput(value: string): string {
  return new Date(value).toISOString()
}

export function fromEvent(e: EventDto): FormState {
  return {
    title: e.title,
    description: e.description,
    important_information: e.important_information,
    starts_at: toLocalInput(e.starts_at),
    ends_at: toLocalInput(e.ends_at),
    places: String(e.places),
    price: (e.price_cents / 100).toFixed(2),
    currency: e.currency,
    location_name: e.location.name,
    address: e.location.address,
    city: e.location.city,
  }
}

export const EMPTY: FormState = {
  title: '',
  description: '',
  important_information: '',
  starts_at: '',
  ends_at: '',
  places: '20',
  price: '0.00',
  currency: 'CHF',
  location_name: '',
  address: '',
  city: '',
}

export function toInput(f: FormState): EventInput {
  return {
    title: f.title.trim(),
    description: f.description,
    important_information: f.important_information,
    starts_at: fromLocalInput(f.starts_at),
    ends_at: fromLocalInput(f.ends_at),
    places: Number(f.places),
    price_cents: Math.round(Number(f.price) * 100),
    currency: f.currency,
    location: { name: f.location_name.trim(), address: f.address.trim(), city: f.city.trim() },
  }
}

/** Only what changed, so a PATCH never re-geocodes an untouched Location. */
export function changedFields(before: EventInput, after: EventInput): Partial<EventInput> {
  const changes: Partial<EventInput> = {}
  for (const key of Object.keys(after) as (keyof EventInput)[]) {
    if (JSON.stringify(before[key]) !== JSON.stringify(after[key])) {
      ;(changes as Record<string, unknown>)[key] = after[key]
    }
  }
  return changes
}

