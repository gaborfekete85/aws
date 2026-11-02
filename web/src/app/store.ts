import { combineReducers, configureStore } from '@reduxjs/toolkit'

const rootReducer = combineReducers({
  app: (state: { name: string } = { name: 'Localbini' }) => state,
})

export function makeStore(preloadedState?: Partial<RootState>) {
  return configureStore({ reducer: rootReducer, preloadedState })
}

export type RootState = ReturnType<typeof rootReducer>
export type AppStore = ReturnType<typeof makeStore>
export type AppDispatch = AppStore['dispatch']
