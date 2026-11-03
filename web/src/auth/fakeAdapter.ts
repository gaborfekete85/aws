import type { AuthAdapter, AuthUser, Role } from './types'

/**
 * In-memory auth for tests and offline development (VITE_AUTH_MODE=fake).
 * Accounts: <anything>@example.com / "Password123!". The local part picks the roles:
 * admin@... -> admin, organizer@... -> organizer, anything else -> Attendee.
 */
const PASSWORD = 'Password123!'
const STORAGE_KEY = 'meeton.fakeAuth'

function rolesFor(email: string): Role[] {
  const local = email.split('@')[0]
  if (local === 'admin') return ['admin']
  if (local === 'organizer') return ['organizer']
  return []
}

function toUser(email: string, name?: string): AuthUser {
  return { sub: `fake-${email}`, email, name: name ?? email.split('@')[0], groups: rolesFor(email) }
}

function load(): AuthUser | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as AuthUser) : null
  } catch {
    return null
  }
}

function save(user: AuthUser | null) {
  try {
    if (user) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    else window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* storage unavailable: session lasts for this page only */
  }
}

export function createFakeAdapter(): AuthAdapter {
  let user: AuthUser | null = load()
  const pending = new Map<string, string>()
  return {
    async currentUser() {
      return user
    },
    async idToken() {
      return user ? `fake-token.${btoa(JSON.stringify(user))}` : null
    },
    async signIn(email, password) {
      if (pending.has(email)) return { kind: 'needsConfirmation' }
      if (password !== PASSWORD) throw new Error('Incorrect username or password.')
      user = toUser(email)
      save(user)
      return { kind: 'signedIn', user }
    },
    async signInWithGoogle() {
      user = toUser('google.user@example.com', 'Google User')
      save(user)
    },
    async signUp(email, password, name) {
      if (password.length < 12) throw new Error('Password must have at least 12 characters.')
      pending.set(email, name)
    },
    async confirmSignUp(email, code) {
      if (code !== '123456') throw new Error('Invalid verification code provided.')
      pending.delete(email)
    },
    async signOut() {
      user = null
      save(null)
    },
  }
}
