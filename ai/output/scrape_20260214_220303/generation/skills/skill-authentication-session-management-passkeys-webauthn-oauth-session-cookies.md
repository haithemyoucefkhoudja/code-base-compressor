# Skill: Authentication & Session Management (Passkeys/WebAuthn, OAuth, Session Cookies)

## Summary
Multi-modal authentication system supporting password-based credentials, WebAuthn/Passkeys (FIDO2), and Google OAuth via the Arctic library. Implements type-safe server actions using ZSA (Zod Server Actions) with Cloudflare Workers KV for session storage, Drizzle ORM for persistence, and React Email for transactional flows. Features include rate-limited endpoints, Turnstile captcha validation, team-based RBAC, and multi-session management with automatic expiration handling.

## Key Components

**Server Actions & Validation**
- `"zsa"::createServerAction::CALL` - Factory for type-safe server actions with chained `.input()` and `.handler()` methods
- `"zsa-react"::useServerAction::CALL` - Client-side hook for executing server actions with `onSuccess`, `onError`, `onStart` callbacks
- `"zsa"::ZSAError::CALL` - Error constructor for validation/authentication failures with `instanceof` type guards
- `Declaration::signUpSchema::CONST`, `Declaration::signInSchema::CONST`, `Declaration::resetPasswordSchema::CONST`, `Declaration::verifyEmailSchema::CONST` - Zod input validation schemas
- `Declaration::googleSSOCallbackSchema::CONST` - OAuth callback validation schema
- `Declaration::catchaSchema::CONST` - Turnstile token validation schema

**Session Management (KV-Based)**
- `Declaration::SESSION_COOKIE_NAME::CONST` - Cookie identifier for session tokens
- `Declaration::GOOGLE_OAUTH_STATE_COOKIE_NAME::CONST`, `Declaration::GOOGLE_OAUTH_CODE_VERIFIER_COOKIE_NAME::CONST` - OAuth PKCE cookie names
- `Declaration::createAndStoreSession::CALL` - Creates session in KV storage with TTL and sets httpOnly cookie
- `Declaration::getSessionFromCookie::CALL` - Retrieves and validates session from request cookies
- `Declaration::deleteKVSession::CALL` - Revokes session by deleting KV entry and clearing cookie
- `Declaration::getSessionsAction::CONST` - Server action to list all active sessions for a user
- `Declaration::MAX_SESSIONS_PER_USER::CONST`, `Declaration::CURRENT_SESSION_VERSION::CONST` - Session limits and schema versioning

**WebAuthn/Passkeys**
- `"@simplewebauthn/browser"::startRegistration::CALL`, `Declaration::startPasskeyRegistrationAction::CONST` - Client/server registration initiation
- `Declaration::verifyRegistrationAction::CONST`, `Declaration::completePasskeyRegistrationAction::CONST` - Server-side verification using `verifyRegistrationResponse`
- `Declaration::generateAuthenticationOptionsAction::CONST` - Generates challenge for authentication
- `Declaration::verifyAuthenticationAction::CONST` - Verifies authentication response
- `"@simplewebauthn/types"::RegistrationResponseJSON`, `"@simplewebauthn/types"::AuthenticationResponseJSON` - Type definitions for WebAuthn responses
- `Declaration::passKeyCredentialTable::CALL` - Database table storing `credentialId`, `credentialPublicKey`, `counter`, `transports`, `aaguid`

**OAuth (Google)**
- `"arctic"::Google` - OAuth provider configuration
- `Declaration::generateState::CALL`, `Declaration::generateCodeVerifier::CALL` - PKCE parameter generation
- `src\app\auth\sso\google\route.ts::GET::DEF` - OAuth initiation endpoint with cookie storage
- `Declaration::googleSSOCallbackAction::CONST` - Callback handler for token exchange and user creation

**Email & Notifications**
- `Declaration::sendResendEmail::CALL`, `Declaration::sendBrevoEmail::CALL`, `Declaration::sendVerificationEmail::CALL` - Transactional email utilities
- `Declaration::TeamInviteEmail::CONST`, `Declaration::ResetPasswordEmail::CONST`, `Declaration::VerifyEmail::CONST` - React Email template components
- `"@react-email/components"::Html::JSX`, `"@react-email/components"::Body::JSX`, `"@react-email/components"::Container::JSX`, `"@react-email/components"::Button::JSX` - Email layout primitives
- `Declaration::EMAIL_VERIFICATION_TOKEN_EXPIRATION_SECONDS::CONST`, `Declaration::PASSWORD_RESET_TOKEN_EXPIRATION_SECONDS::CONST` - Token TTL constants

**Rate Limiting & Security**
- `Declaration::withRateLimit::CALL` - Higher-order function wrapping actions with KV-based rate limiting
- `Declaration::RATE_LIMITS::CALL` - Configuration constants (SIGN_IN, SIGN_UP, EMAIL, PURCHASE, SETTINGS)
- `Declaration::isTurnstileEnabled::CALL`, `Declaration::validateTurnstileToken::CALL` - Cloudflare Turnstile integration
- `Declaration::canSignUp::CALL` - Disposable email domain validation
- `Declaration::hashPassword::CALL` - Password hashing utility (implementation collapsed, referenced in sign-up flows)

**Database Schema (Drizzle ORM)**
- `"@/db/schema"::userTable::CALL` - Core user data with `emailVerified`, `passwordHash`, `googleAccountId`
- `"@/db/schema"::passKeyCredentialTable::CALL` - WebAuthn credential storage
- `"@/db/schema"::teamTable::CALL`, `"@/db/schema"::teamMembershipTable::CALL`, `"@/db/schema"::teamInvitationTable::CALL` - Team/organization structure
- `"@/db/schema"::TEAM_PERMISSIONS::CALL` - RBAC constants (ACCESS_DASHBOARD, CREATE_COMPONENTS, EDIT_COMPONENTS, INVITE_MEMBERS, REMOVE_MEMBERS)

## Behaviors & Rules

**Session Lifecycle**
- Sessions stored in Cloudflare Workers KV with `expirationTtl` calculated as `Math.floor((expiresAt.getTime() - Date.now()) / 1000)` (seconds)
- Session cookies use `httpOnly: true`, `secure: process.env.NODE_ENV === "production"`, `sameSite: "lax"`, and `maxAge` matching KV TTL
- `MAX_SESSIONS_PER_USER` limits concurrent sessions; oldest sessions revoked when limit exceeded
- `CURRENT_SESSION_VERSION` tracked for session schema migrations; incompatible sessions trigger re-authentication
- `isCurrentSession` flag identifies the active session for "logout everywhere" functionality

**Authentication Flows**
- **Password**: Validated against `passwordHash` in `userTable`; successful auth creates KV session with `authenticationType: "password"`
- **Passkey**: Challenge-response flow using `generatePasskeyRegistrationOptions` → `startRegistration` (browser) → `verifyPasskeyRegistration` (server). Credentials stored with `userAgent` and `ipAddress` metadata for display in session list
- **OAuth**: State parameter and PKCE code verifier stored in cookies with 10-minute expiration (`60 * 10`). Callback validates state match before token exchange. New users created automatically with `authenticationType: "oauth"`

**Token Expiration**
- Email verification tokens expire after `EMAIL_VERIFICATION_TOKEN_EXPIRATION_SECONDS`
- Password reset tokens expire after `PASSWORD_RESET_TOKEN_EXPIRATION_SECONDS`  
- Team invitation tokens expire after 7 days (calculated as `Date.now() + 7 * 24 * 60 * 60 * 1000`)
- Credit transactions expire after `CREDITS_EXPIRATION_YEARS` (1 year) with `expirationDate` and `expirationDateProcessedAt` tracking

**Rate Limiting**
- Applied via `withRateLimit` wrapper using `env.NEXT_INC_CACHE_KV` for request counting
- Separate limits for `SIGN_IN`, `SIGN_UP`, `EMAIL` (verification/resend), `PURCHASE`, and `SETTINGS` actions
- Window-based sliding limit with `windowInSeconds` configuration

**Team Permissions**
- `hasTeamPermission` checks `session.teams` array for permission strings
- `requireTeamPermission` throws ZSAError if check fails
- System roles (OWNER, ADMIN) bypass specific permission checks via `isSystemRole` flag
- Team switching updates `selectedTeam` in session context

**Captcha Validation**
- Turnstile enabled via `isTurnstileEnabled()` feature flag checking `process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY`
- Required for `signUpAction` and `resendVerificationAction` when enabled
- Token validated server-side via `validateTurnstileToken` before processing

## Inputs & Outputs

**Server Action Inputs (Zod Schemas)**
- `signUpSchema`: `{ email: z.string().email(), firstName: z.string(), lastName: z.string(), password: z.string().min(8), captchaToken: z.string() }`
- `signInSchema`: `{ email: z.string().email(), password: z.string() }`
- `googleSSOCallbackSchema`: `{ code: z.string(), state: z.string() }`
- `verifyEmailSchema`: `{ token: z.string() }`
- `resetPasswordSchema`: `{ token: z.string(), password: z.string().min(8), confirmPassword: z.string() }` (refined for match)
- Passkey actions: `{ response: z.custom<RegistrationResponseJSON|AuthenticationResponseJSON>(), challenge: z.string(), credentialId: z.string() }`

**Server Action Outputs**
- Success: `{ success: true, session: KVSession }` or `{ success: true, data: T }`
- Error: `ZSAError` thrown with code (`"VALIDATION_ERROR"`, `"INVALID_CREDENTIALS"`, `"RATE_LIMITED"`) and message
- Session object includes: `id`, `userId`, `user` (profile), `teams` (with permissions), `expiresAt`, `authenticationType`, `passkeyCredentialId`, `country`, `city`

**Cookie I/O**
- Input: `cookieStore.get(SESSION_COOKIE_NAME).value` retrieves session token
- Output: `cookieStore.set(SESSION_COOKIE_NAME, token, { expiresAt, httpOnly, secure, sameSite })` sets session
- Output: `cookieStore.delete(SESSION_COOKIE_NAME)` clears on sign-out

**KV Storage Format**
- Key: `session:${sessionId}` (where sessionId derived from token)
- Value: JSON-serialized `KVSession` object
- Metadata: `expirationTtl` calculated from session expiration timestamp

## Dependencies

**Core Framework**
- `zod` - Schema validation
- `zsa`, `zsa-react` - Type-safe server actions
- `drizzle-orm` (sqlite-core, relations) - Database ORM
- `next/headers` (cookies), `next/navigation` (redirect, useRouter), `next/server` (NextResponse)

**Authentication Libraries**
- `@simplewebauthn/browser`, `@simplewebauthn/server`, `@simplewebauthn/types` - WebAuthn/Passkey implementation
- `arctic` - OAuth 2.0 client (Google provider)
- `date-fns` (formatDistanceToNow, format) - Session time formatting

**Infrastructure**
- Cloudflare Workers KV (`env.NEXT_INC_CACHE_KV`) - Session storage and rate limiting counters
- `@react-email/components`, `react-email` - Email templating
- `sonner` - Toast notifications for auth feedback
- `lucide-react` (Shield, LogOut, etc.) - Security UI icons

## Code Patterns

### ZSA Server Action with Rate Limiting
```typescript
"use server";

import { createServerAction, ZSAError } from "zsa";
import { z } from "zod";
import { withRateLimit, RATE_LIMITS } from "@/utils/with-rate-limit";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export const signInAction = createServerAction()
  .input(schema)
  .handler(async ({ input }) => {
    return withRateLimit(async () => {
      const user = await db.query.userTable.findFirst({ 
        where: eq(userTable.email, input.email) 
      });
      
      if (!user || !await verifyPassword(input.password, user.passwordHash)) {
        throw new ZSAError("INVALID_CREDENTIALS", "Invalid email or password");
      }
      
      const session = await createAndStoreSession(user.id, "password");
      return { success: true, session };
    }, RATE_LIMITS.SIGN_IN);
  });
```

### Client-Side Action Execution
```typescript
"use client";

import { useServerAction } from "zsa-react";
import { signInAction } from "@/app/actions/auth";
import { ZSAError } from "zsa";

export function SignInPage() {
  const { execute, isPending, error } = useServerAction(signInAction, {
    onSuccess: ({ session }) => {
      router.push("/dashboard");
    },
    onError: (err) => {
      if (err instanceof ZSAError) {
        toast.error(err.message);
      }
    },
  });
  
  return <form onSubmit={(e) => {
    e.preventDefault();
    execute({ email, password });
  }} />;
}
```

### KV Session Creation with Cookie
```typescript
export async function createAndStoreSession(
  userId: string,
  authenticationType: "password" | "passkey" | "oauth",
  passkeyCredentialId?: string
) {
  const sessionToken = generateSessionToken(); // nanoid(32)
  const sessionId = generateSessionId(sessionToken);
  const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
  
  const session: KVSession = {
    id: sessionId,
    userId,
    user: await getUserData(userId),
    teams: await getUserTeamsWithPermissions(userId),
    expiresAt,
    expiration: expiresAt,
    version: CURRENT_SESSION_VERSION,
    authenticationType,
    passkeyCredentialId,
    isCurrentSession: true,
  };
  
  await kv.put(`session:${sessionId}`, JSON.stringify(session), {
    expirationTtl: Math.floor((expiresAt.getTime() - Date.now()) / 1000),
  });
  
  await setSessionTokenCookie({ token: sessionToken, expiresAt });
  return session;
}
```

### WebAuthn Registration Flow
```typescript
// Server: Generate options
export const generateRegistrationOptionsAction = createServerAction()
  .input(z.object({ email: z.string().email() }))
  .handler(async ({ input }) => {
    const options = await generatePasskeyRegistrationOptions(input.email);
    return { options };
  });

// Client: Start registration
import { startRegistration } from "@simplewebauthn/browser";

async function handleRegister() {
  const { options } = await generateRegistrationOptionsAction({ email });
  const response = await startRegistration(options);
  await completePasskeyRegistrationAction({ response, email });
}

// Server: Verify and store
export const completePasskeyRegistrationAction = createServerAction()
  .input(z.object({ 
    response: z.custom<RegistrationResponseJSON>(),
    email: z.string().email() 
  }))
  .handler(async ({ input }) => {
    const verification = await verifyPasskeyRegistration({
      response: input.response,
      expectedChallenge: storedChallenge,
      expectedOrigin: process.env.ORIGIN!,
      expectedRPID: process.env.RPID!,
    });
    
    if (verification.verified && verification.registrationInfo) {
      await db.insert(passKeyCredentialTable).values({
        userId: user.id,
        credentialId: verification.registrationInfo.credential.id,
        credentialPublicKey: Buffer.from(verification.registrationInfo.credential.publicKey).toString("base64"),
        counter: verification.registrationInfo.credential.counter,
        transports: input.response.response.transports?.join(","),
      });
    }
  });
```

### OAuth Google Initiation
```typescript
// src/app/auth/sso/google/route.ts
import { Google } from "arctic";
import { generateState, generateCodeVerifier } from "arctic";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const google = new Google(
  process.env.GOOGLE_CLIENT_ID!,
  process.env.GOOGLE_CLIENT_SECRET!,
  process.env.GOOGLE_REDIRECT_URI!
);

export async function GET() {
  const state = generateState();
  const codeVerifier = generateCodeVerifier();
  const url = await google.createAuthorizationURL(state, codeVerifier, {
    scopes: ["profile", "email"],
  });
  
  const cookieStore = await cookies();
  cookieStore.set(GOOGLE_OAUTH_STATE_COOKIE_NAME, state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 10, // 10 minutes
    sameSite: "lax",
  });
  cookieStore.set(GOOGLE_OAUTH_CODE_VERIFIER_COOKIE_NAME, codeVerifier, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 10,
    sameSite: "lax",
  });
  
  return NextResponse.redirect(url);
}
```

### Multi-Session Management UI
```typescript
// src/app/settings/settings/sessions/sessions_client.tsx
"use client";

import { useServerAction } from "zsa-react";
import { deleteSessionAction } from "@/app/actions/auth";
import { formatDistanceToNow } from "date-fns";

export function SessionsClient({ sessions }: { sessions: SessionWithMeta[] }) {
  const { execute } = useServerAction(deleteSessionAction);
  
  return (
    <DataTable
      columns={[
        { accessorKey: "userAgent", header: "Device" },
        { 
          accessorKey: "createdAt", 
          header: "Created",
          cell: ({ row }) => formatDistanceToNow(row.original.createdAt, { addSuffix: true })
        },
        {
          id: "actions",
          cell: ({ row }) => (
            <Button 
              variant="destructive" 
              onClick={() => execute({ sessionId: row.original.id })}
              disabled={row.original.isCurrent}
            >
              Revoke
            </Button>
          )
        }
      ]}
      data={sessions}
    />
  );
}
```