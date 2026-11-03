import type { AppDispatch } from '../../app/store'
import { bookingsApi } from './bookingsApi'

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Payments creates the Stripe session asynchronously (on BookingRequested), so
 * the Checkout URL may not exist yet: poll until it does.
 */
export async function waitForCheckoutUrl(
  dispatch: AppDispatch,
  bookingId: string,
  { attempts = 20, delayMs = 500 }: { attempts?: number; delayMs?: number } = {},
): Promise<string> {
  for (let i = 0; i < attempts; i++) {
    const result = await dispatch(
      bookingsApi.endpoints.getCheckout.initiate(bookingId, { forceRefetch: true, subscribe: false }),
    )
    const checkout = result.data
    if (checkout && checkout.status !== 'creating') {
      if (checkout.status === 'open' && checkout.url) return checkout.url
      throw new Error('This Checkout is no longer open.')
    }
    if (result.error && (result.error as { status?: number }).status !== 202) {
      throw new Error('Could not start Checkout.')
    }
    await sleep(checkout && 'retry_after_ms' in checkout ? checkout.retry_after_ms : delayMs)
  }
  throw new Error('Checkout is taking longer than expected. Find it later in My Bookings.')
}
