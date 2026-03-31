# Skill: Email System with React Email Templates

## Summary
This skill implements a provider-agnostic transactional email system using React Email for type-safe, component-based template composition. The system supports dual backend providers (Resend and Brevo/Sendinblue) with environment-based selection, and exposes rate-limited sending utilities for verification, password reset, and team invitation workflows. All templates use consistent visual styling through React Email components, rendering to static HTML for transport while maintaining type safety through TypeScript interfaces.

## Key Components
- **`VerifyEmail`** (`src/react-email/verify-email.tsx`): React Email template for email verification with `verificationLink` and `username` props.
- **`ResetPasswordEmail`** (`src/react-email/reset-password.tsx`): React Email template for password reset flows with `resetLink` and `username` props.
- **`TeamInviteEmail`** (`src/react-email/team-invite.tsx`): React Email template for team invitations with `inviteLink`, `recipientEmail`, `teamName`, and `inviterName` props.
- **`sendResendEmail`** (`Declaration::sendResendEmail::CALL`): Provider-specific implementation using Resend SDK with `RESEND_API_KEY`.
- **`sendBrevoEmail`** (`Declaration::sendBrevoEmail::CALL`): Provider-specific implementation using Brevo REST API with `BREVO_API_KEY`.
- **`getEmailProvider`** (`Declaration::getEmailProvider::CALL`): Environment-based provider selector returning `'resend'` | `'brevo'`.
- **`sendVerificationEmail`**: Public API wrapping verification template rendering and provider dispatch with rate limiting.
- **`sendTeamInvitationEmail`**: Public API wrapping team invite template rendering and provider dispatch with rate limiting.
- **`sendPasswordResetEmail`**: Public API wrapping password reset template rendering and provider dispatch with rate limiting.
- **`render`** (`'@react-email/render'::render::CALL`): React Email renderer converting JSX templates to HTML strings.
- **`withRateLimit`** (`"@/utils/with-rate-limit"::withRateLimit::CALL`): Rate limiting wrapper applied to all send operations.
- **`RATE_LIMITS.EMAIL`** (`"@/utils/with-rate-limit"::RATE_LIMITS.EMAIL::CALL`): Specific rate limit bucket for email operations.

## Behaviors & Rules
- **Provider Selection**: Defaults to `'resend'` when `EMAIL_PROVIDER` environment variable is unset; reads from `process.env.EMAIL_PROVIDER`.
- **Rate Limiting**: All public send functions (`sendVerificationEmail`, `sendTeamInvitationEmail`, `sendPasswordResetEmail`) must be wrapped with `withRateLimit` using `RATE_LIMITS.EMAIL` bucket.
- **Template Styling Consistency**: All templates use `backgroundColor: '#f6f9fc'` on Body, white Container (`#ffffff`) with `padding: '40px'` and `borderRadius: '8px'`, and primary action buttons with `backgroundColor: '#0070f3'`.
- **URL Construction**: 
  - Verification: `${baseUrl}/auth/verify-email?token=${verificationToken}`
  - Team Invite: `${baseUrl}/auth/team-invite?token=${invitationToken}`
  - Password Reset: `${baseUrl}/auth/reset-password?token=${resetToken}`
- **Resend Payload Format**: Requires `to: string[]`, `subject`, `html`, and maps `tags` to array of `{name, value}` objects. Uses `from: process.env.EMAIL_FROM || 'noreply@example.com'`.
- **Brevo Payload Format**: Requires `to` mapped to array of `{email}` objects, `subject`, `htmlContent` (not `html`), and `tags` as string array. Uses sender object with email from environment.
- **Environment Dependencies**: 
  - `RESEND_API_KEY` (for Resend provider)
  - `BREVO_API_KEY` (for Brevo provider)
  - `NEXT_PUBLIC_APP_URL` (falls back to `'http://localhost:3000'`)
  - `EMAIL_FROM` (falls back to `'noreply@example.com'`)
  - `EMAIL_REPLY_TO` (optional)
  - `EMAIL_FROM_NAME` (optional)
- **Error Handling**: Brevo implementation checks `response.ok` and throws on failure; Resend relies on SDK error throwing.
- **Template Props Validation**: Each template has strict TypeScript interface (e.g., `VerifyEmailProps`, `ResetPasswordEmailProps`, `TeamInviteEmailProps`).

## Inputs & Outputs
**Template Props Interfaces:**
- `VerifyEmailProps`: `{ verificationLink: string; username: string; }`
- `ResetPasswordEmailProps`: `{ resetLink: string; username: string; }`
- `TeamInviteEmailProps`: `{ inviteLink: string; recipientEmail: string; teamName: string; inviterName: string; }`

**Send Function Inputs:**
- `sendVerificationEmail`: `{ email: string; verificationToken: string; username: string; }` → `Promise<void>`
- `sendTeamInvitationEmail`: `{ email: string; invitationToken: string; teamName: string; inviterName: string; }` → `Promise<void>`
- `sendPasswordResetEmail`: `{ email: string; resetToken: string; username: string; }` → `Promise<void>`

**Provider Function Inputs:**
- `sendResendEmail`: `{ to: string[]; subject: string; html: string; tags?: string[]; }` → `Promise<void>`
- `sendBrevoEmail`: `{ to: string[]; subject: string; htmlContent: string; tags?: string[]; }` → `Promise<void>`

**Rendering Output:**
- `render(ReactElement)` → `Promise<string>` (HTML string suitable for email transport)

## Dependencies
- **`@react-email/components`**: Provides `Html`, `Head`, `Body`, `Container`, `Heading`, `Text`, `Link`, `Section` JSX components for template composition.
- **`@react-email/render`**: Provides `render` function for static HTML generation from React Email components.
- **`@/utils/with-rate-limit`**: Provides `withRateLimit` wrapper and `RATE_LIMITS` constants for email rate limiting.
- **`resend`**: Resend SDK (dynamically imported in `sendResendEmail`).
- **Environment Variables**: `RESEND_API_KEY`, `BREVO_API_KEY`, `NEXT_PUBLIC_APP_URL`, `EMAIL_FROM`, `EMAIL_REPLY_TO`, `EMAIL_FROM_NAME`.

## Code Patterns

### React Email Template Structure
```typescript
// src/react-email/verify-email.tsx
import { Html, Head, Body, Container, Heading, Text, Link } from '@react-email/components';

interface VerifyEmailProps {
  verificationLink: string;
  username: string;
}

export const VerifyEmail = ({ verificationLink, username }: VerifyEmailProps) => {
  return (
    <Html>
      <Head />
      <Body style={{ backgroundColor: '#f6f9fc', padding: '20px 0' }}>
        <Container style={{ backgroundColor: '#ffffff', padding: '40px', borderRadius: '8px' }}>
          <Heading style={{ color: '#333', fontSize: '24px', marginBottom: '20px' }}>
            Verify your email address
          </Heading>
          <Text style={{ color: '#555', fontSize: '16px', lineHeight: '24px' }}>
            Hi {username},
          </Text>
          <Link 
            href={verificationLink}
            style={{ 
              display: 'inline-block', 
              padding: '12px 24px', 
              backgroundColor: '#0070f3', 
              color: '#ffffff', 
              textDecoration: 'none',
              borderRadius: '6px',
              marginTop: '20px'
            }}
          >
            Verify Email
          </Link>
        </Container>
      </Body>
    </Html>
  );
};
```

### Provider-Agnostic Send Implementation
```typescript
// src/utils/email.ts
import { render } from '@react-email/render';
import { withRateLimit, RATE_LIMITS } from '@/utils/with-rate-limit';

const getEmailProvider = (): 'resend' | 'brevo' => {
  return (process.env.EMAIL_PROVIDER as 'resend' | 'brevo') || 'resend';
};

const sendResendEmail = async ({ to, subject, html, tags }: {
  to: string[]; subject: string; html: string; tags?: string[];
}) => {
  const resend = new (await import('resend')).Resend(process.env.RESEND_API_KEY);
  await resend.emails.send({
    from: process.env.EMAIL_FROM || 'noreply@example.com',
    to,
    subject,
    html,
    tags: tags?.map(tag => ({ name: tag, value: tag })),
  });
};

const sendBrevoEmail = async ({ to, subject, htmlContent, tags }: {
  to: string[]; subject: string; htmlContent: string; tags?: string[];
}) => {
  const response = await fetch('https://api.brevo.com/v3/smtp/email', {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'api-key': process.env.BREVO_API_KEY!,
    },
    body: JSON.stringify({
      sender: { email: process.env.EMAIL_FROM || 'noreply@example.com' },
      to: to.map(email => ({ email })),
      subject,
      htmlContent,
      tags,
    }),
  });
  if (!response.ok) throw new Error(`Brevo API error: ${response.statusText}`);
};

export const sendVerificationEmail = async ({
  email, verificationToken, username
}: { email: string; verificationToken: string; username: string }) => {
  return withRateLimit(async () => {
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
    const verificationLink = `${baseUrl}/auth/verify-email?token=${verificationToken}`;
    const html = await render(VerifyEmail({ verificationLink, username }));
    
    const provider = getEmailProvider();
    if (provider === 'resend') {
      await sendResendEmail({ to: [email], subject: 'Verify your email address', html, tags: ['verification'] });
    } else {
      await sendBrevoEmail({ to: [email], subject: 'Verify your email address', htmlContent: html, tags: ['verification'] });
    }
  }, RATE_LIMITS.EMAIL);
};
```