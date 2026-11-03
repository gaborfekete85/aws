const dateFormat = new Intl.DateTimeFormat('en-GB', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Europe/Zurich',
})

export function formatWhen(iso: string): string {
  return dateFormat.format(new Date(iso))
}

export function formatPrice(cents: number, currency: string): string {
  if (cents === 0) return 'Free'
  return new Intl.NumberFormat('en-CH', { style: 'currency', currency }).format(cents / 100)
}

export function formatDistance(km: number | null | undefined): string | null {
  if (km === null || km === undefined) return null
  return km < 1 ? `${Math.round(km * 1000)} m away` : `${km.toFixed(1)} km away`
}

/** yyyy-mm-dd for <input type="date"> in the user's local day. */
export function isoDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}
