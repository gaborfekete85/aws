import { config } from '../config'
import { amplifyAdapter } from './amplifyAdapter'
import { createFakeAdapter } from './fakeAdapter'
import type { AuthAdapter } from './types'

export const authAdapter: AuthAdapter = config.authMode === 'fake' ? createFakeAdapter() : amplifyAdapter

export type { AuthAdapter, AuthUser, Role } from './types'
