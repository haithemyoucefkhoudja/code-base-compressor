# Skill: Rate Limiting System with KV Storage

## Summary
A fixed-window rate limiting implementation using Vercel KV (Redis) storage to protect server actions and API endpoints. The system wraps async functions with atomic counter increments and automatic expiration, enforcing distinct limits for sensitive operations like authentication, purchases, and email sending. When limits are exceeded, it throws standard Errors to be caught by the calling server action handlers.

## Key Components

- **`withRateLimit<T>`**: Higher-order async function that wraps operations with rate limit checks
- **`RATE_LIMITS`**: Configuration constant defining operation-specific limits and window durations
- **`RateLimitConfig`**: Interface specifying `key` (string identifier), `limit` (max requests), and `window` (duration in seconds)
- **`kv`**: Vercel KV client instance from `@vercel/kv` providing atomic `get`, `incr`, and `expire` operations
- **Rate Limit Keys**: Namespaced keys following pattern `rate_limit:{operation_type}` (e.g., `rate_limit:email`)

## Behaviors & Rules

- **Fixed Window Algorithm**: Uses atomic `kv.incr()` to count requests and `kv.expire()` to set window duration
- **Default Window**: 60 seconds (configurable per operation type)
- **Limit Enforcement**: Checks current count via `kv.get()`; if `current >= limit`, throws `Error('Rate limit exceeded')`
- **Atomic Operations**: Relies on Vercel KV atomicity for `incr` to prevent race conditions during concurrent requests
- **Key Expiration**: Automatically expires counter keys after the window duration to reset limits
- **Operation Types**: Five predefined categories with distinct limits:
  - `SETTINGS`: 10 requests per 60s (configuration changes)
  - `PURCHASE`: 5 requests per 60s (credit/package purchases)
  - `EMAIL`: 20 requests per 60s (verification, invitation, password reset emails)
  - `SIGN_IN`: 5 requests per 60s (authentication attempts)
  - `SIGN_UP`: 3 requests per 60s (registration attempts)
- **Error Handling**: Throws generic Error instances that propagate to server action error boundaries
- **Missing Key Handling**: Defaults to 0 when key does not exist in KV (`await kv.get<number>(key) || 0`)

## Inputs & Outputs

**`withRateLimit(fn, config)`**:
- **Input `fn`**: `() => Promise<T>` - The async operation to rate limit
- **Input `config`**: `RateLimitConfig` object containing:
  - `key`: String identifier for the rate limit bucket (e.g., `'rate_limit:email'`)
  - `limit`: Number of allowed requests in the window (e.g., `20`)
  - `window`: Duration in seconds before counter resets (e.g., `60`)
- **Output**: `Promise<T>` - Resolves with the return value of `fn` if within limits
- **Throws**: `Error` with message `'Rate limit exceeded'` when limit reached

**`RATE_LIMITS` Constant**:
- **Type**: Record<string, RateLimitConfig>
- **Values**: Pre-configured objects for SETTINGS, PURCHASE, EMAIL, SIGN_IN, SIGN_UP operations

## Dependencies

- **`@vercel/kv`**: External package providing Redis-compatible KV storage client
- **Server Action Context**: Designed to wrap server actions (zsa pattern observed in usage)
- **Environment**: Requires Vercel KV binding configured in environment (implied by import)

## Code Patterns

**Basic Wrapper Pattern**:
```typescript
import { withRateLimit, RATE_LIMITS } from "@/utils/with-rate-limit";

export const sendVerificationEmail = async (params: {
  email: string;
  verificationToken: string;
  username: string;
}) => {
  return withRateLimit(async () => {
    // Email sending implementation
    const html = await render(VerifyEmail({ ... }));
    await sendResendEmail({ to: [params.email], html });
  }, RATE_LIMITS.EMAIL);
};
```

**Configuration Definition**:
```typescript
export const RATE_LIMITS = {
  SETTINGS: { key: 'rate_limit:settings', limit: 10, window: 60 },
  PURCHASE: { key: 'rate_limit:purchase', limit: 5, window: 60 },
  EMAIL: { key: 'rate_limit:email', limit: 20, window: 60 },
  SIGN_IN: { key: 'rate_limit:sign_in', limit: 5, window: 60 },
  SIGN_UP: { key: 'rate_limit:sign_up', limit: 3, window: 60 },
};
```

**Core Implementation Logic**:
```typescript
export async function withRateLimit<T>(
  fn: () => Promise<T>,
  config: { key: string; limit: number; window: number }
): Promise<T> {
  const { key, limit, window } = config;
  const current = await kv.get<number>(key) || 0;
  
  if (current >= limit) {
    throw new Error('Rate limit exceeded');
  }
  
  await kv.incr(key);
  await kv.expire(key, window);
  return fn();
}
```