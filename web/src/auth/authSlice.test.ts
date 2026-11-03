import { makeStore } from '../app/store'
import { confirmRegistration, login, logout, register } from './authSlice'
import { createFakeAdapter } from './fakeAdapter'
import { groupsFromClaim } from './types'

const setup = () => makeStore({ auth: createFakeAdapter() })

describe('auth slice', () => {
  it('signs in with email and password and picks up roles', async () => {
    const store = setup()
    await store.dispatch(login({ email: 'organizer@example.com', password: 'Password123!' }))
    const { auth } = store.getState()
    expect(auth.status).toBe('signedIn')
    expect(auth.user?.groups).toEqual(['organizer'])
  })

  it('keeps the error message on a failed sign in', async () => {
    const store = setup()
    await store.dispatch(login({ email: 'ada@example.com', password: 'wrong' }))
    expect(store.getState().auth.error).toBe('Incorrect username or password.')
    expect(store.getState().auth.user).toBeNull()
  })

  it('registers, asks for confirmation, then lets the user log in', async () => {
    const store = setup()
    await store.dispatch(register({ email: 'new@example.com', password: 'Password123!', name: 'New' }))
    expect(store.getState().auth.pendingConfirmationFor).toBe('new@example.com')

    await store.dispatch(login({ email: 'new@example.com', password: 'Password123!' }))
    expect(store.getState().auth.status).not.toBe('signedIn') // not confirmed yet

    await store.dispatch(confirmRegistration({ email: 'new@example.com', code: '123456' }))
    expect(store.getState().auth.pendingConfirmationFor).toBeNull()
    await store.dispatch(login({ email: 'new@example.com', password: 'Password123!' }))
    expect(store.getState().auth.status).toBe('signedIn')
  })

  it('logs out', async () => {
    const store = setup()
    await store.dispatch(login({ email: 'ada@example.com', password: 'Password123!' }))
    await store.dispatch(logout())
    expect(store.getState().auth).toMatchObject({ status: 'signedOut', user: null })
  })
})

describe('groupsFromClaim', () => {
  it.each([
    [['admin', 'organizer'], ['admin', 'organizer']],
    ['organizer', ['organizer']],
    [['organizer', 'unknown'], ['organizer']],
    [undefined, []],
  ])('%j -> %j', (claim, expected) => {
    expect(groupsFromClaim(claim)).toEqual(expected)
  })
})
