# Skill: Cloudflare KV Session Management with D1 Database

## Summary
This skill implements a hybrid session management system using Cloudflare KV for fast, edge-distributed session storage and D1 for persistent database backup. It employs a dual-write strategy where sessions are written to both KV (with TTL expiration) and D1 (as source of truth), enabling high-performance session validation at the edge while maintaining data durability. The system supports cross-device session synchronization, session versioning for cache invalidation, and automatic fallback from KV to D1 on cache misses.

## Key Components

- **KVSession**: Interface/type defining the session structure stored in KV, including `id`, `userId`, `expiresAt`, `user` (denormalized user data), `teams` (denormalized team memberships), `version` (timestamp), `authenticationType`, `passkeyCredentialId`, `country`, `city`, and `isCurrentSession`.
- **getSessionKey**: Utility function generating KV keys with pattern `session:{userId}:{sessionId}`.
- **getKVSession**: Retrieves session from Cloudflare KV (fast path).
- **updateKVSession**: Writes session to KV with expiration TTL and optional user/team data denormalization.
- **deleteKVSession**: Removes session from KV (logout/revocation).
- **getAllSessionIdsOfUser**: Lists all session keys for a user using KV list operations with prefix `session:{userId}:`.
- **updateAllSessionsOfUser**: Cross-device synchronization function that updates all KV sessions for a user when profile or team data changes.
- **createSession**: Server-side function implementing dual-write strategy (D1 insert + KV put).
- **getSessionFromCookie**: Cookie-based session retrieval with KV-first lookup and D1 fallback.
- **SESSION_COOKIE_NAME**: Constant defining the HTTP-only cookie name (`session_token`).
- **MAX_SESSIONS_PER_USER**: Constant limiting concurrent sessions (value: 5).
- **CURRENT_SESSION_VERSION**: Constant for session schema versioning.
- **env.NEXT_INC_CACHE_KV**: Cloudflare KV binding accessed via environment or `getCloudflareContext`.

## Behaviors & Rules

- **KV Key Pattern**: All session keys follow strict format `session:{userId}:{sessionId}` to enable efficient prefix-based listing for cross-device operations.
- **Dual-Write Strategy**: Every session creation or update writes to D1 first (source of truth), then to KV with matching expiration TTL. KV serves read-heavy operations; D1 handles persistence and complex queries.
- **TTL Management**: KV entries use `expirationTtl` calculated as seconds until `expiresAt` date. D1 stores the absolute `expiresAt` timestamp.
- **Cross-Device Sync**: When user profile or team memberships change, `updateAllSessionsOfUser` fetches all session keys by prefix, retrieves each from KV, updates the denormalized user/team data, and re-writes to KV without changing session IDs.
- **KV-to-D1 Fallback**: `getSessionFromCookie` attempts KV retrieval first; on miss or expiration, queries D1 and optionally rehydrates KV (healing pattern).
- **Session ID Generation**: Format `{userId}_{timestamp}_{random}` ensures uniqueness and enables parsing userId from token without database lookup.
- **Denormalized Data**: KV stores user details (email, names, credits, verification status) and team arrays to avoid D1 joins on every request.
- **Version Tracking**: Each session carries a `version` timestamp (Date.now()) to track freshness and support cache invalidation strategies.
- **Session Limits**: System enforces `MAX_SESSIONS_PER_USER` (5) to prevent abuse; oldest sessions are evicted when limit exceeded.
- **Cookie Security**: Session cookies are HTTP-only, Secure in production, SameSite=lax, with expiration matching session TTL.

## Inputs & Outputs

**Inputs:**
- `userId` (string): User identifier for session association
- `sessionId` (string): Unique session identifier (format: `{userId}_{timestamp}_{random}`)
- `expiresAt` (Date): Absolute expiration timestamp
- `authenticationType` (enum): "password" | "passkey" | "google" | "github"
- `passkeyCredentialId` (optional string): WebAuthn credential reference
- `country` / `city` (optional strings): Geolocation data
- `KVSessionUser` object: Denormalized user subset (id, email, firstName, lastName, emailVerified, currentCredits, createdAt, updatedAt, lastCreditRefreshAt)
- `teams` array: Denormalized team memberships (id, name, slug, roleId)

**Outputs:**
- `KVSession` object: Complete session payload from KV
- `SessionValidationResult` tuple: `{ session: KVSession, user: KVSessionUser }`
- Session key strings (format: `session:{userId}:{sessionId}`)
- Array of session metadata objects from `getAllSessionIdsOfUser` (key names and absolute expirations)

## Dependencies

- **@opennextjs/cloudflare**: Provides `getCloudflareContext()` for accessing KV and D1 bindings in Next.js runtime
- **drizzle-orm**: D1 database client for SQL operations (`db.insert`, `db.query`, `db.update`)
- **next/headers**: Cookie store API for session token management (`cookies().set()`, `cookies().get()`, `cookies().delete()`)
- **zustand**: State management for client-side session cache (via `useSessionStore`)
- **Crypto API**: `crypto.randomUUID()` for secure session token generation

## Code Patterns

### Session Key Generation
```typescript
export function getSessionKey(userId: string, sessionId: string): string {
  return `session:${userId}:${sessionId}`;
}
```

### Dual-Write Session Creation
```typescript
export async function createSession(params: CreateSessionParams): Promise<KVSession> {
  const sessionId = generateSessionId(params.userId);
  const token = generateSessionToken();
  const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
  
  // Write to D1 (source of truth)
  await db.insert(sessionTable).values({
    id: sessionId,
    userId: params.userId,
    token,
    expiresAt,
    authenticationType: params.authenticationType,
    passkeyCredentialId: params.passkeyCredentialId,
    country: params.country,
    city: params.city,
    createdAt: new Date(),
    updatedAt: new Date(),
  });
  
  // Fetch user for denormalization
  const user = await db.query.userTable.findFirst({
    where: eq(userTable.id, params.userId),
  });
  
  // Write to KV (fast access layer)
  const session = await updateKVSession(
    params.userId,
    sessionId,
    expiresAt,
    { /* KVSessionUser fields */ },
    [] // teams
  );
  
  return session;
}
```

### KV Session Retrieval with D1 Fallback
```typescript
export async function getSessionFromCookie(): Promise<SessionValidationResult | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("session_token")?.value;
  if (!token) return null;
  
  const userId = token.split("_")[0];
  
  // Fast path: KV lookup
  const kvSession = await getKVSession(userId, token);
  if (kvSession && new Date(kvSession.expiresAt) > new Date()) {
    return { session: kvSession, user: kvSession.user };
  }
  
  // Fallback: D1 query
  const dbSession = await db.query.sessionTable.findFirst({
    where: eq(sessionTable.id, token),
    with: { user: true },
  });
  
  if (!dbSession || dbSession.expiresAt < new Date()) return null;
  
  // Optional: Rehydrate KV (healing pattern)
  // await updateKVSession(...)
  
  return { session: dbSession as KVSession, user: dbSession.user };
}
```

### Cross-Device Session Synchronization
```typescript
export async function updateAllSessionsOfUser(userId: string): Promise<void> {
  const sessionIds = await getAllSessionIdsOfUser(userId);
  const kv = env.NEXT_INC_CACHE_KV;
  
  // Fetch fresh data from D1
  const user = await db.query.userTable.findFirst({
    where: eq(userTable.id, userId),
  });
  
  const memberships = await db.query.teamMembershipTable.findMany({
    where: eq(teamMembershipTable.userId, userId),
    with: { team: true },
  });
  
  const teams = memberships.map(m => ({
    id: m.team.id,
    name: m.team.name,
    slug: m.team.slug,
    roleId: m.roleId,
  }));
  
  // Update all KV sessions
  for (const { key } of sessionIds) {
    const existing = await kv.get<KVSession>(key, "json");
    if (existing) {
      const updated: KVSession = {
        ...existing,
        user: { /* updated user fields */ },
        teams,
        version: Date.now(),
      };
      await kv.put(key, JSON.stringify(updated));
    }
  }
}
```

### KV Operations with TTL
```typescript
export async function updateKVSession(
  userId: string,
  sessionId: string,
  expiresAt: Date,
  user: KVSessionUser,
  teams: KVSession["teams"]
): Promise<KVSession | null> {
  const key = getSessionKey(userId, sessionId);
  const kv = env.NEXT_INC_CACHE_KV;
  
  const session: KVSession = {
    id: sessionId,
    userId,
    expiresAt,
    user,
    teams,
    version: Date.now(),
    authenticationType: "password",
    isCurrentSession: false,
  };
  
  await kv.put(key, JSON.stringify(session), {
    expirationTtl: Math.floor((expiresAt.getTime() - Date.now()) / 1000),
  });
  
  return session;
}
```