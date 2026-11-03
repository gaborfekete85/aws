export interface Place {
  lat: number
  lng: number
  label: string
}

const NOMINATIM = 'https://nominatim.openstreetmap.org/search'

/** Free-text place → coordinates (OpenStreetMap Nominatim; CORS-enabled, keyless). */
export async function geocodePlace(query: string, signal?: AbortSignal): Promise<Place | null> {
  const url = `${NOMINATIM}?${new URLSearchParams({ q: query, format: 'jsonv2', limit: '1' })}`
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) throw new Error(`Place lookup failed (${response.status})`)
  const results = (await response.json()) as { lat: string; lon: string; display_name: string }[]
  if (!results.length) return null
  const [first] = results
  return { lat: Number(first.lat), lng: Number(first.lon), label: first.display_name }
}

/** The browser's location (asks the Visitor for permission). */
export function currentPosition(): Promise<Place> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new Error('Location is not available in this browser'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude, label: 'Your location' }),
      () => reject(new Error('Location permission was denied')),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
    )
  })
}
