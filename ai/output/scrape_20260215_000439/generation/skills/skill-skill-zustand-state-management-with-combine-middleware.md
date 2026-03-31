# Skill: Zustand State Management with Combine Middleware

## Summary
This skill implements type-safe global state management using Zustand's `combine` middleware, which separates initial state definitions from action creators. The pattern creates distinct store hooks (e.g., `useSessionStore`, `useConfigStore`) that manage specific domain state—ranging from feature flags like `isGoogleSSOEnabled` to complex session objects with nested user data—while providing immutable update utilities through the `set` and `get` functions passed to the action creator.

## Key Components
- **`'zustand'::create::CALL`** - Factory function that instantiates the store when wrapped with middleware
- **`'zustand/middleware'::combine::CALL`** - Middleware that accepts `(initialState, (set, get) => actions)` and returns a store creator
- **`useConfigStore`** - Manages feature toggle flags (`isGoogleSSOEnabled`, `isTurnstileEnabled`)
- **`useNavStore`** - Manages navigation UI state (`isOpen`) with toggle actions
- **`useSessionStore`** - Manages authenticated session state including `userId`, `user` object (with `currentCredits`, `emailVerified`, `createdAt`, `updatedAt`, `firstName`, `lastName`, `email`, `id`), `expiresAt`, `isCurrentSession`, `country`, `city`, `teams` array, `passkeyCredentialId`, `version`, `expiration`, and `authenticationType`
- **`useTransactionStore`** - Manages transaction refresh triggers via `refreshTrigger` counter
- **`StoreApi`** - Type reference for the underlying store API
- **`UseBoundStore`** - Type reference for the bound store hook return type

## Behaviors & Rules
- **State/Action Separation**: The `combine` middleware strictly separates the initial state object (first argument) from the action creator function (second argument), improving TypeScript inference for both state shape and action methods.
- **Shallow Merge Updates**: The `set` function performs shallow merges of the provided object into the existing state; to update nested properties (like `user.currentCredits`), the pattern uses immutable spread: `set((state) => ({ user: state.user ? { ...state.user, currentCredits: credits } : null }))`.
- **Previous State Access**: Actions requiring the current state (e.g., toggles, increments) use the functional `set` form: `set((state) => ({ refreshTrigger: state.refreshTrigger + 1 }))`.
- **Partial Resets**: The `clearSession` action demonstrates partial state reset by explicitly setting specific fields to initial values (`userId: ''`, `user: null`, `isCurrentSession: false`) rather than calling a reset method.
- **Boolean Toggles**: Simple boolean state uses direct setters (`setGoogleSSOEnabled: (enabled: boolean) => set({ isGoogleSSOEnabled: enabled })`) or computed toggles (`toggle: () => set((state) => ({ isOpen: !state.isOpen }))`).
- **Null Safety**: When updating nested user properties, actions check for null (`state.user ? { ...state.user, currentCredits: credits } : null`) to prevent runtime errors during session clearing.

## Inputs & Outputs
- **Inputs**:
  - `initialState`: Plain object defining default values for all state properties (e.g., `{ isGoogleSSOEnabled: false, isTurnstileEnabled: false }`)
  - `createActions`: Function receiving `(set, get, api)` that returns an object of action methods
- **Outputs**: 
  - React hook (e.g., `useSessionStore`) returning the combined state and actions
  - `StoreApi` instance providing imperative access to `setState`, `getState`, and `subscribe`

## Dependencies
- `zustand` - Core state management library
- `zustand/middleware` - Provides the `combine` middleware utility

## Code Patterns

**Basic Store Definition Pattern:**
```typescript
import { create } from 'zustand';
import { combine } from 'zustand/middleware';

export const useConfigStore = create(
  combine(
    {
      isGoogleSSOEnabled: false,
      isTurnstileEnabled: false,
    },
    (set, get) => ({
      setGoogleSSOEnabled: (enabled: boolean) => set({ isGoogleSSOEnabled: enabled }),
      setTurnstileEnabled: (enabled: boolean) => set({ isTurnstileEnabled: enabled }),
    })
  )
);
```

**Complex Session Store with Nested Updates:**
```typescript
export const useSessionStore = create(
  combine(
    {
      userId: '',
      user: null,
      expiresAt: new Date(),
      isCurrentSession: false,
      country: '',
      city: '',
      teams: [],
      passkeyCredentialId: null,
      version: 0,
      expiration: new Date(),
      authenticationType: '',
    },
    (set, get) => ({
      setSession: (session) => set(session),
      clearSession: () => set({
        userId: '',
        user: null,
        isCurrentSession: false,
      }),
      updateUserCredits: (credits: number) => set((state) => ({
        user: state.user ? { ...state.user, currentCredits: credits } : null
      })),
    })
  )
);
```

**Counter/Refresh Trigger Pattern:**
```typescript
export const useTransactionStore = create(
  combine(
    {
      refreshTrigger: 0,
    },
    (set, get) => ({
      triggerRefresh: () => set((state) => ({ 
        refreshTrigger: state.refreshTrigger + 1 
      })),
      setRefreshTrigger: (value: number) => set({ refreshTrigger: value }),
    })
  )
);
```

**Navigation Toggle Pattern:**
```typescript
export const useNavStore = create(
  combine(
    {
      isOpen: false,
    },
    (set, get) => ({
      toggle: () => set((state) => ({ isOpen: !state.isOpen })),
      setIsOpen: (isOpen: boolean) => set({ isOpen }),
    })
  )
);
```