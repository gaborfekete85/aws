import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import type { AuthAdapter, AuthUser } from './types'

export interface AuthState {
  status: 'unknown' | 'loading' | 'signedIn' | 'signedOut'
  user: AuthUser | null
  error: string | null
  pendingConfirmationFor: string | null
}

const initialState: AuthState = {
  status: 'unknown',
  user: null,
  error: null,
  pendingConfirmationFor: null,
}

type ThunkConfig = { extra: { auth: AuthAdapter } }

const message = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong')

export const loadSession = createAsyncThunk<AuthUser | null, void, ThunkConfig>(
  'auth/loadSession',
  (_, { extra }) => extra.auth.currentUser(),
)

export const login = createAsyncThunk<
  { user: AuthUser | null; confirmFor: string | null },
  { email: string; password: string },
  ThunkConfig
>('auth/login', async ({ email, password }, { extra }) => {
  const result = await extra.auth.signIn(email, password)
  return result.kind === 'signedIn'
    ? { user: result.user, confirmFor: null }
    : { user: null, confirmFor: email }
})

export const register = createAsyncThunk<
  string,
  { email: string; password: string; name: string },
  ThunkConfig
>('auth/register', async ({ email, password, name }, { extra }) => {
  await extra.auth.signUp(email, password, name)
  return email
})

export const confirmRegistration = createAsyncThunk<
  void,
  { email: string; code: string },
  ThunkConfig
>('auth/confirm', ({ email, code }, { extra }) => extra.auth.confirmSignUp(email, code))

export const loginWithGoogle = createAsyncThunk<void, void, ThunkConfig>(
  'auth/google',
  (_, { extra }) => extra.auth.signInWithGoogle(),
)

export const logout = createAsyncThunk<void, void, ThunkConfig>('auth/logout', (_, { extra }) =>
  extra.auth.signOut(),
)

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError(state) {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadSession.pending, (state) => {
        state.status = 'loading'
      })
      .addCase(loadSession.fulfilled, (state, { payload }) => {
        state.user = payload
        state.status = payload ? 'signedIn' : 'signedOut'
      })
      .addCase(loadSession.rejected, (state) => {
        state.user = null
        state.status = 'signedOut'
      })
      .addCase(login.pending, (state) => {
        state.error = null
      })
      .addCase(login.fulfilled, (state, { payload }) => {
        state.user = payload.user
        state.status = payload.user ? 'signedIn' : 'signedOut'
        state.pendingConfirmationFor = payload.confirmFor
      })
      .addCase(login.rejected, (state, { error }) => {
        state.error = error.message ?? 'Sign in failed'
      })
      .addCase(register.fulfilled, (state, { payload }) => {
        state.pendingConfirmationFor = payload
        state.error = null
      })
      .addCase(register.rejected, (state, { error }) => {
        state.error = error.message ?? 'Registration failed'
      })
      .addCase(confirmRegistration.fulfilled, (state) => {
        state.pendingConfirmationFor = null
        state.error = null
      })
      .addCase(confirmRegistration.rejected, (state, { error }) => {
        state.error = error.message ?? 'Confirmation failed'
      })
      .addCase(logout.fulfilled, (state) => {
        state.user = null
        state.status = 'signedOut'
      })
  },
})

export const { clearError } = authSlice.actions
export const authReducer = authSlice.reducer
export { message as errorMessage }

export const selectUser = (s: { auth: AuthState }) => s.auth.user
export const selectIsOrganizer = (s: { auth: AuthState }) =>
  !!s.auth.user && (s.auth.user.groups.includes('organizer') || s.auth.user.groups.includes('admin'))
export const selectIsAdmin = (s: { auth: AuthState }) => !!s.auth.user?.groups.includes('admin')
