# Skill: Captcha System with Turnstile Integration

## Summary
A conditional CAPTCHA verification system using Cloudflare Turnstile that integrates with React forms via Zod validation. The system features environment-based configuration (public site key for client-side rendering, secret key for server-side validation), feature flag control for conditional activation, and seamless integration with react-hook-form for user registration and authentication flows.

## Key Components

**Captcha Component** (`src/components/captcha.tsx`)
- Conditionally renders Turnstile widget based on `isTurnstileEnabled` feature flag
- Props: `validationError?: string`, `onSuccess?: (token: string) => void`
- Returns `null` if feature disabled or site key missing

**Validation Utility** (`src/utils/validate-captcha.ts`)
- Server-side token verification against Cloudflare API
- Function: `validateTurnstileToken(token: string): Promise<boolean>`
- Endpoint: `https://challenges.cloudflare.com/turnstile/v0/siteverify`

**Schema Definition** (`src/lib/schemas.ts`)
- `catchaSchema`: Zod object requiring `captchaToken` (min 1 character)
- Extended into `signUpSchema` and other authentication schemas

**Feature Flag** (`src/flags.ts`)
- `isTurnstileEnabled(): Promise<boolean>`
- Checks for presence of `NEXT_PUBLIC_TURNSTILE_SITE_KEY` environment variable

**Environment Configuration**
- `NEXT_PUBLIC_TURNSTILE_SITE_KEY`: Client-side site key for widget rendering
- `TURNSTILE_SECRET_KEY`: Server-side secret for token validation

## Behaviors & Rules

- **Conditional Activation**: The Captcha component only renders if `isTurnstileEnabled()` returns true AND `NEXT_PUBLIC_TURNSTILE_SITE_KEY` is defined
- **Dual-Key Security**: Public key (site key) used for client widget initialization; secret key used exclusively server-side for validation
- **Token Validation Flow**: Client obtains token via Turnstile widget → token stored in form state → submitted to server → server validates against Cloudflare API before processing form
- **Error Handling**: Validation errors display via `validationError` prop; server validation failures return `false` and should trigger form submission prevention
- **Form Integration**: On successful verification, `onSuccess` callback receives token and typically calls `form.setValue("captchaToken", token)` to update react-hook-form state
- **Schema Enforcement**: Zod schema rejects empty/undefined captcha tokens with message "Please complete the CAPTCHA verification"
- **Graceful Degradation**: If feature flag is disabled, component returns `null` and form submission proceeds without CAPTCHA (development/testing scenarios)

## Inputs & Outputs

**Captcha Component**
- Inputs:
  - `validationError?: string` - Error message to display below widget
  - `onSuccess?: (token: string) => void` - Callback invoked with verification token
- Outputs: JSX.Element | null

**validateTurnstileToken**
- Input: `token: string` - The Turnstile response token
- Output: `Promise<boolean>` - True if validation succeeds, false if invalid or error

**catchaSchema (Zod)**
- Input: Object with `captchaToken: string`
- Validation: Token must have length >= 1
- Error Message: "Please complete the CAPTCHA verification"

## Dependencies

- `react-turnstile` (or equivalent Turnstile React wrapper) - Client widget rendering
- `@/flags` - Feature flag detection (`isTurnstileEnabled`)
- `zod` - Schema validation (`catchaSchema`)
- `@hookform/resolvers/zod` - Zod integration with react-hook-form
- `react-hook-form` - Form state management (typical usage pattern)
- `@/components/ui/form` - Form field wrapper components (Form, FormField, FormControl, FormMessage)

## Code Patterns

**Component Usage in Forms**
```typescript
<FormField
  control={form.control}
  name="captchaToken"
  render={({ field }) => (
    <FormItem>
      <FormControl>
        <Captcha
          onSuccess={(token) => {
            form.setValue("captchaToken", token);
          }}
          validationError={form.formState.errors.captchaToken?.message}
        />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

**Server-Side Validation**
```typescript
const isValid = await validateTurnstileToken(input.captchaToken);
if (!isValid) {
  throw new Error("CAPTCHA validation failed");
}
```

**Schema Definition**
```typescript
export const catchaSchema = z.object({
  captchaToken: z.string().min(1, "Please complete the CAPTCHA verification"),
});

export const signUpSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  captchaToken: catchaSchema.shape.captchaToken,
});
```

**Feature Flag Check**
```typescript
export async function isTurnstileEnabled(): Promise<boolean> {
  return process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY !== undefined;
}
```

**Environment Variables**
```env
NEXT_PUBLIC_TURNSTILE_SITE_KEY=0x4AAAAAA...
TURNSTILE_SECRET_KEY=0x4AAAAAA...
```