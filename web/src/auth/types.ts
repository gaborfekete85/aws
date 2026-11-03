export type Role = 'admin' | 'organizer'

export interface AuthUser {
  sub: string
  email: string
  name?: string
  groups: Role[]
}

export type SignInResult = { kind: 'signedIn'; user: AuthUser } | { kind: 'needsConfirmation' }

/** The port the UI talks to; Amplify in production, a fake in tests and offline dev. */
export interface AuthAdapter {
  currentUser(): Promise<AuthUser | null>
  idToken(): Promise<string | null>
  signIn(email: string, password: string): Promise<SignInResult>
  signInWithGoogle(): Promise<void>
  signUp(email: string, password: string, name: string): Promise<void>
  confirmSignUp(email: string, code: string): Promise<void>
  signOut(): Promise<void>
}

export function groupsFromClaim(claim: unknown): Role[] {
  const raw = Array.isArray(claim) ? claim : typeof claim === 'string' ? claim.split(/[\s,]+/) : []
  return raw.filter((g): g is Role => g === 'admin' || g === 'organizer')
}
