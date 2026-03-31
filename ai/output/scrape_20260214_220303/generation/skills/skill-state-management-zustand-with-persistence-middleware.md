# Skill: State Management (Zustand with Persistence/Middleware)

## Summary
This codebase implements global state management using Zustand with the `combine` middleware to create type-safe stores that separate state definitions from action implementations. The pattern is used across four distinct domain stores—navigation (`useNavStore`), session (`useSessionStore`), configuration (`useConfigStore`), and transaction/credit management (`useTransactionStore`)—providing centralized state for UI toggles, authentication state, feature flags, and workflow data. State updates follow strict TypeScript contracts through the `combine` middleware pattern, with boolean toggles for UI state (dialogs, sidebars, loading states) and direct value assignments for entity selection (teams, nodes, packages).

## Key Components
- **`'zustand'::create::CALL`** - Core store factory function used to instantiate all global stores.
- **`'zustand/middleware'::combine::CALL`** - Middleware for type-safe separation of initial state and action definitions.
- **`"@/state/nav"::useNavStore::CALL`** - Navigation state store managing sidebar open/close states.
- **`"@/state/session"::useSessionStore::CALL`** - Session store managing user authentication state, loading status, and logout actions.
- **`"@/state/config"::useConfigStore::CALL`** - Configuration store for runtime feature flags (Google SSO, Turnstile).
- **`"@/state/transaction"::useTransactionStore::CALL`** - Transaction/credit state store for billing and workflow transactions.
- **`Declaration::UseBoundStore::CALL`** - Type reference for bound store instances.
- **State Setter Patterns:**
  - `Declaration::setIsDialogOpen::CALL`, `Declaration::setIsCollapsed::CALL`, `Declaration::setOpenMobile::CALL`, `Declaration::setOpen::CALL` - Boolean UI state toggles.
  - `Declaration::setSearch::CALL`, `Declaration::setName::CALL`, `Declaration::setPage::CALL` - String/number value updates.
  - `Declaration::setSelectedNodeId::CALL`, `Declaration::setSelectedTeam::CALL`, `Declaration::setSelectedPackage::CALL` - Entity selection state.
  - `Declaration::setIsLoading::CALL`, `Declaration::setIsSaving::CALL`, `Declaration::setIsGenerating::CALL`, `Declaration::setIsProcessing::CALL`, `Declaration::setIsRegistering::CALL`, `Declaration::setIsAuthenticating::CALL` - Async operation status flags.
  - `Declaration::setNodes::CALL`, `Declaration::setEdges::CALL`, `Declaration::setPendingInvitations::CALL` - Array state management for collections.
  - `Declaration::toggleSidebar::CALL`, `Declaration::toggleCollapsed::CALL` - Toggle actions using functional updates.

## Behaviors & Rules
- **Combine Middleware Pattern**: All stores must be created using `create(combine(initialState, (set) => actions))` to ensure type safety between state and actions.
- **Strict Typing**: State interfaces (e.g., `ConfigState`, `NavState`, `SessionState`) explicitly define the shape of stored data, with `unknown` types used for dynamic data (like session user objects) when strict typing is deferred.
- **Boolean Toggle Convention**: UI state toggles (sidebars, dialogs, loading states) use functional updates `set((state) => ({ isOpen: !state.isOpen }))` for toggle actions and direct object updates `set({ isOpen: value })` for explicit assignments.
- **Store Segregation by Domain**: State is strictly separated by domain—navigation state never mixes with session state; configuration flags are isolated from transaction data.
- **Hook Consumption**: Stores are accessed exclusively through generated hooks (e.g., `useNavStore()`) with selectors for performance optimization where applicable.
- **Null Initialization**: Entity selection states (selected team, selected node) initialize as `null` and are set to string IDs when active.
- **Action Naming**: Setters follow camelCase with `set` prefix (e.g., `setIsLoading`, `setSelectedTeam`), while toggles use verb prefixes (e.g., `toggleSidebar`).

## Inputs & Outputs
**Inputs:**
- **Initial State Objects**: Typed state definitions passed to `combine` (e.g., `{ isGoogleSSOEnabled: false, isTurnstileEnabled: false }`).
- **Setter Functions**: `(set)` function provided by Zustand to create actions that mutate state.
- **Action Implementations**: Functions that call `set()` with either direct values or functional updates.

**Outputs:**
- **Store Hooks**: `useNavStore`, `useSessionStore`, `useConfigStore`, `useTransactionStore` returning bound store instances.
- **State Values**: Boolean flags (isOpen, isLoading), string identifiers (selectedTeam, selectedNodeId), arrays (nodes, edges, pendingInvitations).
- **Action Callbacks**: Typed setter functions (e.g., `setIsDialogOpen: (open: boolean) => void`) consumed by React components.

## Dependencies
- **`zustand`**: Core state management library providing the `create` function.
- **`zustand/middleware`**: Provides the `combine` middleware for type-safe store creation.
- **React**: Required for consuming stores via hooks in components.
- **TypeScript**: Used for strict typing of state interfaces and action definitions.

## Code Patterns

**Store Creation with Combine Middleware:**
```typescript
import { create } from 'zustand';
import { combine } from 'zustand/middleware';

interface ConfigState {
  isGoogleSSOEnabled: boolean;
  isTurnstileEnabled: boolean;
}

export const useConfigStore = create(
  combine(
    {
      isGoogleSSOEnabled: false,
      isTurnstileEnabled: false,
    } as ConfigState,
    (set) => ({
      setGoogleSSOEnabled: (enabled: boolean) => 
        set({ isGoogleSSOEnabled: enabled }),
      setTurnstileEnabled: (enabled: boolean) => 
        set({ isTurnstileEnabled: enabled }),
    })
  )
);
```

**Navigation Store with Toggle Pattern:**
```typescript
interface NavState {
  isOpen: boolean;
}

export const useNavStore = create(
  combine(
    { isOpen: false } as NavState,
    (set) => ({
      setNavOpen: (isOpen: boolean) => set({ isOpen }),
      toggleNav: () => set((state) => ({ isOpen: !state.isOpen })),
    })
  )
);
```

**Session Store with Complex State:**
```typescript
interface SessionState {
  user: unknown | null;
  session: unknown | null;
  isLoading: boolean;
}

export const useSessionStore = create(
  combine(
    {
      user: null,
      session: null,
      isLoading: false,
    } as SessionState,
    (set) => ({
      setUser: (user: unknown) => set({ user }),
      setSession: (session: unknown) => set({ session }),
      setLoading: (isLoading: boolean) => set({ isLoading }),
      logout: () => set({ user: null, session: null }),
    })
  )
);
```

**Component Usage Pattern:**
```typescript
// Boolean state consumption
const { isOpen, toggleNav } = useNavStore();

// Entity selection with null safety
const { setSelectedTeam, setSelectedNodeId } = useStore();
setSelectedTeam("team_123");
setSelectedNodeId(null);

// Async operation status
const { setIsLoading, setIsSaving } = useSessionStore();
setIsLoading(true);
setIsSaving(false);

// Array state updates
const { setNodes, setEdges } = useTransactionStore();
setNodes(newNodes);
setEdges(newEdges);
```