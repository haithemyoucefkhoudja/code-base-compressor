# Skill: Authentication & Session Management (Passkeys, OAuth, Custom Session)

## Summary
This skill implements a multi-modal authentication system supporting password-based credentials, WebAuthn/Passkeys, and Google OAuth SSO, backed by a custom KV-based session store. The system uses ZSA (Type-Safe Server Actions) for server-side logic, Drizzle ORM for persistence, and implements strict security controls including rate limiting, disposable email validation, and HTTP-only session cookies. Sessions are stored in KV storage with TTL expiration and include rich context (user teams, permissions, authentication method metadata) to support multi-tenant authorization.

## Key Components

**Core Authentication Actions**
- `signInAction` - Password-based authentication with rate limiting
- `signUpAction` - User registration with email verification and disposable email checks
- `signOutAction` - Session invalidation and cookie clearing
- `googleSSOCallbackAction` - Google OAuth callback handler with state verification
- `verifyEmailAction` - Email verification token validation
- `resendVerificationAction` - Rate-limited email resend
- `forgotPasswordAction` / `resetPasswordAction` - Password reset flow with time-limited tokens

**Passkey/WebAuthn Actions**
- `startPasskeyRegistrationAction` - Generates WebAuthn registration options with challenge storage
- `completePasskeyRegistrationAction` - Verifies and stores passkey credentials
- `verifyPasskeyRegistrationAction` - Server-side verification using `@simplewebauthn/server`
- `generateAuthenticationOptionsAction` - Creates authentication challenges for passkey sign-in
- `verifyAuthenticationAction` - Validates passkey authentication responses
- `deletePasskeyAction` - Removes passkey credentials with ownership verification

**Session Management Utilities**
- `createAndStoreSession` - Creates session in KV storage and sets HTTP-only cookie
- `getSessionFromCookie` - Validates session from cookie against KV store
- `clearSession` - Deletes session from KV and clears browser cookie
- `generateSessionToken` - Cryptographically secure token generation using Web Crypto API
- `setSessionTokenCookie` - Cookie setting with security flags (httpOnly, secure, sameSite)
- `updateAllSessionsOfUser` - Batch session updates (e.g., permission changes)
- `deleteKVSession` / `updateKVSession` - Direct KV session manipulation

**Database Schema (Drizzle ORM)**
- `userTable` - Stores email, passwordHash, emailVerified, googleAccountId, currentCredits, lastCreditRefreshAt, signUpIpAddress
- `passKeyCredentialTable` - Stores credentialId, credentialPublicKey, counter, transports, aaguid, userAgent, ipAddress with foreign key to userTable
- `teamTable` / `teamMembershipTable` / `teamInvitationTable` - Multi-tenant authorization schema
- `creditTransactionTable` - Billing/credit system integration
- Relations: `userRelations`, `passKeyCredentialRelations`, `teamRelations`, `teamMembershipRelations`

**Client Components**
- `PasskeyRegistrationButton` - Initiates WebAuthn registration flow
- `PasskeyAuthenticationButton` - Handles passkey sign-in with challenge-response
- `PasskeysList` - Displays and manages user passkeys with delete capability
- `SSOButtons` - Google OAuth initiation with PKCE
- `SessionsClient` - Active session management UI with revoke functionality
- `EmailVerificationDialog` - Email verification prompt with resend capability

**Security & Validation**
- `withRateLimit` - Rate limiting wrapper with configurable windows (SIGN_UP, SIGN_IN, EMAIL, SETTINGS, PURCHASE)
- `canSignUp` - Disposable email detection and existing user checks
- `requireVerifiedEmail` - Middleware enforcing email verification
- `requireAdmin` - Role-based access control
- `hashPassword` / `verifyPassword` - Password hashing utilities
- `validateTurnstileToken` - Captcha verification

## Behaviors & Rules

**Session Lifecycle**
- Sessions are stored in KV storage with a TTL calculated from `absoluteExpiration` (default 30 days)
- Session cookies use `httpOnly`, `secure` (in production), `sameSite: "lax"`, and `path: "/"`
- Session tokens are SHA-256 hashed before use as KV keys to prevent session ID enumeration
- Sessions include `authenticationType` (password | passkey | google), `passkeyCredentialId` (for passkey sessions), and `teams` array with permissions for multi-tenant context
- `MAX_SESSIONS_PER_USER` (5) limits concurrent sessions per user
- Session validation checks both KV existence and `absoluteExpiration` timestamp; expired sessions are deleted from KV

**Passkey/WebAuthn Rules**
- Registration challenges are stored in KV with 5-minute TTL (`expirationTtl: 300`)
- Credentials store `counter` to prevent replay attacks; incremented on each authentication
- `transports` array stored as JSONB for credential mobility tracking
- `aaguid` captured for authenticator metadata (vendor, model)
- IP address and user agent logged during registration for audit trails
- Passkey deletion requires ownership verification against `session.userId`

**OAuth (Google) Flow**
- State parameter stored in `GOOGLE_OAUTH_STATE_COOKIE_NAME` cookie for CSRF protection
- PKCE code verifier stored in `GOOGLE_OAUTH_CODE_VERIFIER_COOKIE_NAME`
- Google accounts linked via `googleAccountId` field in `userTable`
- OAuth sessions marked with `authenticationType: "google"`

**Email Verification & Security**
- Verification tokens use `getVerificationTokenKey` prefix (`verify:${token}`) with 24-hour TTL
- Password reset tokens use `getResetTokenKey` prefix (`reset:${token}`) with 1-hour TTL
- `EMAIL_VERIFICATION_TOKEN_EXPIRATION_SECONDS` constant defines verification window
- `canSignUp` checks against disposable email domains via KV lookup (`disposable-email:${domain}`)
- Sign-up IP address stored in `signUpIpAddress` for fraud detection

**Rate Limiting**
- `RATE_LIMITS.SIGN_UP`: 5 requests per 60 seconds
- `RATE_LIMITS.SIGN_IN`: 5 requests per 60 seconds  
- `RATE_LIMITS.EMAIL`: 2 requests per 300 seconds (verification resend)
- `RATE_LIMITS.SETTINGS`: 10 requests per 60 seconds
- `RATE_LIMITS.PURCHASE`: 5 requests per 60 seconds

**Multi-Tenant Authorization**
- `getUserTeamsWithPermissions` loads team memberships with role permissions into session context
- `hasTeamPermission` checks if user has specific permission in any team
- `requireTeamPermission` throws `ZSAError("FORBIDDEN")` if permission missing
- Team invitations use unique tokens with expiration; acceptance creates `teamMembershipTable` entry

**Credit System Integration**
- `currentCredits` and `lastCreditRefreshAt` stored in user table
- `shouldRefreshCredits` logic checks if monthly refresh is due
- Credit transactions linked to user with `remainingAmount` tracking for partial usage

## Inputs & Outputs

**Session Creation**
- Input: `{ userId: string, authenticationType: "password" | "passkey" | "google", passkeyCredentialId?: string }`
- Output: `Promise<void>` (sets cookie as side effect)
- KV Storage: Key `session:${hashedToken}`, Value `KVSession` object with TTL

**Passkey Registration**
- Input: `{ response: RegistrationResponseJSON, challenge: string, userAgent?: string, ipAddress?: string }`
- Output: `{ success: boolean, credentialId: string }`
- Database: Insert into `passKeyCredentialTable` with `credentialPublicKey` (base64), `counter`, `transports`, `aaguid`

**Google OAuth Callback**
- Input: `code: string, state: string` (from query params)
- Output: `{ success: boolean, userId: string }` or redirect to error page
- Side Effects: Creates/updates user, establishes session, redirects to `REDIRECT_AFTER_SIGN_IN`

**Session Validation**
- Input: `sessionToken` from cookie
- Output: `{ session: KVSession | null, user: User | null }`
- Logic: Parses cookie, hashes token, queries KV, checks expiration, fetches fresh user data

**Rate Limiting**
- Input: `fn: () => Promise<T>, config: { key: string, maxRequests: number, windowSeconds: number }`
- Output: `Promise<T>` or throws rate limit error
- Storage: KV key `rate-limit:${key}:${identifier}` with sliding window

## Dependencies

**Core Libraries**
- `zsa` - Type-safe server actions with input validation
- `zod` - Schema validation for all inputs
- `drizzle-orm` - Database ORM with SQLite/PostgreSQL dialects
- `@simplewebauthn/server` - WebAuthn server-side verification
- `@simplewebauthn/browser` - Client-side WebAuthn APIs
- `arctic` - OAuth 2.0 client for Google SSO
- `@paralleldrive/cuid2` - ID generation for database records

**Infrastructure**
- KV Storage (Vercel KV or Cloudflare KV) - Session persistence and rate limiting
- Resend/Brevo - Transactional email delivery
- Turnstile - Bot protection (captcha)

**UI Dependencies**
- `sonner` - Toast notifications for auth feedback
- `@radix-ui/react-dialog` - Dialog primitives for auth modals
- `next/headers` - Cookie manipulation in server actions
- `next/navigation` - Redirects after authentication

## Code Patterns

**Server Action with ZSA and Rate Limiting**
```typescript
export const signInAction = createServerAction()
  .input(signInSchema)
  .handler(async ({ input }) => {
    return withRateLimit(async () => {
      const user = await db.query.userTable.findFirst({
        where: eq(userTable.email, input.email)
      });
      
      if (!user || !await verifyPassword(input.password, user.passwordHash)) {
        throw new ZSAError("NOT_FOUND", "Invalid credentials");
      }
      
      await createAndStoreSession(user.id, "password");
      return { success: true, userId: user.id };
    }, RATE_LIMITS.SIGN_IN);
  });
```

**KV Session Creation with Teams Context**
```typescript
export async function createAndStoreSession(
  userId: string,
  authenticationType: "password" | "passkey" | "google",
  passkeyCredentialId?: string
): Promise<void> {
  const token = generateSessionToken();
  const sessionId = await generateSessionId(token); // SHA-256 hash
  const absoluteExpiration = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
  
  const teams = await getUserTeamsWithPermissions(userId);
  
  const sessionObj: KVSession = {
    userId,
    authenticationType,
    passkeyCredentialId,
    absoluteExpiration,
    teams
  };
  
  await kv.put(`session:${sessionId}`, JSON.stringify(sessionObj), {
    expirationTtl: Math.floor((absoluteExpiration.getTime() - Date.now()) / 1000)
  });
  
  await setSessionTokenCookie({ token, expires: absoluteExpiration });
}
```

**Passkey Registration Flow**
```typescript
export const completePasskeyRegistrationAction = createServerAction()
  .input(passkeyRegistrationSchema)
  .handler(async ({ input }) => {
    const { session } = await getSessionFromCookie();
    if (!session) throw new ZSAError("UNAUTHORIZED");
    
    const verification = await verifyPasskeyRegistration({
      userId: session.userId,
      response: input.response,
      challenge: input.challenge,
      userAgent: headers().get("user-agent"),
      ipAddress: await getIP()
    });
    
    if (!verification.verified) {
      throw new ZSAError("VERIFICATION_FAILED");
    }
    
    return { 
      success: true, 
      credentialId: verification.registrationInfo.credential.id 
    };
  });
```

**Session Validation with User Data Refresh**
```typescript
export async function getSessionFromCookie(): Promise<{ 
  session: KVSession | null; 
  user: User | null 
}> {
  const cookieStore = await cookies();
  const token = cookieStore.get("session-token")?.value;
  
  if (!token) return { session: null, user: null };
  
  const sessionId = await generateSessionId(token);
  const sessionData = await kv.get(`session:${sessionId}`);
  
  if (!sessionData) return { session: null, user: null };
  
  const session: KVSession = JSON.parse(sessionData);
  
  if (new Date() > new Date(session.absoluteExpiration)) {
    await kv.delete(`session:${sessionId}`);
    return { session: null, user: null };
  }
  
  const user = await getUserFromDB(session.userId);
  return { session, user };
}
```

**Team Permission Check**
```typescript
export async function hasTeamPermission(
  userId: string, 
  permission: string
): Promise<boolean> {
  const teams = await getUserTeamsWithPermissions(userId);
  return teams.some(t => t.permissions.includes(permission));
}

// Usage in server action
export const inviteUserAction = createServerAction()
  .input(inviteUserSchema)
  .handler(async ({ input }) => {
    const hasPermission = await hasTeamPermission(input.teamId, "INVITE_MEMBERS");
    if (!hasPermission) {
      throw new ZSAError("FORBIDDEN", "Insufficient permissions");
    }
    // ... invitation logic
  });
```

**Cookie Security Configuration**
```typescript
export async function setSessionTokenCookie(params: { 
  token: string; 
  expires: Date; 
  isSecure?: boolean 
}): Promise<void> {
  const { token, expires, isSecure = true } = params;
  const cookieStore = await cookies();
  
  cookieStore.set("session-token", token, {
    httpOnly: true,
    secure: isSecure,
    sameSite: "lax",
    expires,
    path: "/"
  });
}
```