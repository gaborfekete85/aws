import { Amplify } from 'aws-amplify'
import {
  confirmSignUp,
  fetchAuthSession,
  signIn,
  signInWithRedirect,
  signOut,
  signUp,
} from 'aws-amplify/auth'
import { config } from '../config'
import { groupsFromClaim, type AuthAdapter, type AuthUser } from './types'

let configured = false

function configure() {
  if (configured) return
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
  configured = true
}

async function userFromSession(): Promise<AuthUser | null> {
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
    configure()
    try {
      return await userFromSession()
    } catch {
      return null
    }
  },
  async idToken() {
    configure()
    const session = await fetchAuthSession()
    return session.tokens?.idToken?.toString() ?? null
  },
  async signIn(email, password) {
    configure()
    const result = await signIn({ username: email, password })
    if (result.nextStep.signInStep === 'CONFIRM_SIGN_UP') return { kind: 'needsConfirmation' }
    const user = await userFromSession()
    if (!user) throw new Error('Signed in but no session was returned')
    return { kind: 'signedIn', user }
  },
  async signInWithGoogle() {
    configure()
    await signInWithRedirect({ provider: 'Google' })
  },
  async signUp(email, password, name) {
    configure()
    await signUp({ username: email, password, options: { userAttributes: { email, name } } })
  },
  async confirmSignUp(email, code) {
    configure()
    await confirmSignUp({ username: email, confirmationCode: code })
  },
  async signOut() {
    configure()
    await signOut()
  },
}
