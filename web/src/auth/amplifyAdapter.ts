import { config } from '../config'
import { groupsFromClaim, type AuthAdapter, type AuthUser } from './types'

/**
 * Amplify is loaded on demand (dynamic import) so the search page renders before
 * the Cognito SDK has downloaded (#38: it is the largest dependency of the app).
 */
let auth: Promise<typeof import('aws-amplify/auth')> | null = null

function amplify(): Promise<typeof import('aws-amplify/auth')> {
  auth ??= (async () => {
    const { Amplify } = await import('aws-amplify')
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: config.cognito.userPoolId,
          userPoolClientId: config.cognito.userPoolClientId,
          loginWith: {
            email: true,
            oauth: {
              domain: config.cognito.domain,
              scopes: ['openid', 'email', 'profile'],
              redirectSignIn: [`${config.webUrl}/auth/callback`],
              redirectSignOut: [`${config.webUrl}/`],
              responseType: 'code',
              providers: ['Google'],
            },
          },
        },
      },
    })
    return import('aws-amplify/auth')
  })()
  return auth
}

async function userFromSession(): Promise<AuthUser | null> {
  const { fetchAuthSession } = await amplify()
  const session = await fetchAuthSession()
  const payload = session.tokens?.idToken?.payload
  if (!payload?.sub) return null
  return {
    sub: String(payload.sub),
    email: String(payload.email ?? ''),
    name: payload.name ? String(payload.name) : undefined,
    groups: groupsFromClaim(payload['cognito:groups']),
  }
}

export const amplifyAdapter: AuthAdapter = {
  async currentUser() {
    try {
      return await userFromSession()
    } catch {
      return null
    }
  },
  async idToken() {
    const { fetchAuthSession } = await amplify()
    const session = await fetchAuthSession()
    return session.tokens?.idToken?.toString() ?? null
  },
  async signIn(email, password) {
    const { signIn } = await amplify()
    const result = await signIn({ username: email, password })
    if (result.nextStep.signInStep === 'CONFIRM_SIGN_UP') return { kind: 'needsConfirmation' }
    const user = await userFromSession()
    if (!user) throw new Error('Signed in but no session was returned')
    return { kind: 'signedIn', user }
  },
  async signInWithGoogle() {
    const { signInWithRedirect } = await amplify()
    await signInWithRedirect({ provider: 'Google' })
  },
  async signUp(email, password, name) {
    const { signUp } = await amplify()
    await signUp({ username: email, password, options: { userAttributes: { email, name } } })
  },
  async confirmSignUp(email, code) {
    const { confirmSignUp } = await amplify()
    await confirmSignUp({ username: email, confirmationCode: code })
  },
  async signOut() {
    const { signOut } = await amplify()
    await signOut()
  },
}
