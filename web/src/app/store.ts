import { combineReducers, configureStore } from '@reduxjs/toolkit'
import { baseApi } from '../api/baseApi'
import { authAdapter, type AuthAdapter } from '../auth'
import { authReducer } from '../auth/authSlice'

const rootReducer = combineReducers({
  auth: authReducer,
  [baseApi.reducerPath]: baseApi.reducer,
})

export type RootState = ReturnType<typeof rootReducer>

export function makeStore(options: { preloadedState?: Partial<RootState>; auth?: AuthAdapter } = {}) {
  return configureStore({
    reducer: rootReducer,
    preloadedState: options.preloadedState,
    middleware: (getDefault) =>
      getDefault({ thunk: { extraArgument: { auth: options.auth ?? authAdapter } } }).concat(
        baseApi.middleware,
      ),
  })
}

export type AppStore = ReturnType<typeof makeStore>
export type AppDispatch = AppStore['dispatch']
