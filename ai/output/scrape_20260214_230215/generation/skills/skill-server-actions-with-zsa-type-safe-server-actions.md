# Skill: Server Actions with ZSA (Type-Safe Server Actions)

## Summary
A pattern for building type-safe Next.js Server Actions using the ZSA library, which enforces input validation through Zod schemas and provides end-to-end type safety between server-side action handlers and client-side React hooks. The pattern establishes a consistent contract where server actions are created via `createServerAction()`, validated with `.input(zodSchema)`, and consumed via the `useServerAction` hook with structured error handling via `ZSAError` codes.

## Key Components

**Core ZSA Primitives:**
- `"zsa"::createServerAction::CALL` - Factory function to initialize server action builders
- `"zsa"::createServerAction.input::CALL` - Chain method to attach Zod input schemas
- `"zsa"::createServerAction.input.handler::CALL` - Chain method to register the async handler with input validation
- `"zsa"::createServerAction.handler::CALL` - Chain method for actions without input validation
- `"zsa"::ZSAError::CALL` - Error constructor for typed error codes
- `"zsa"::instanceof ZSAError::CALL` - Runtime error type checking
- `"zsa-react"::useServerAction::CALL` - React hook for consuming server actions with pending states and callbacks

**Validation Schemas (Zod):**
- `"zod"::z.object::CALL` - Primary schema builder for action inputs
- `"zod"::z.string::CALL`, `"zod"::z.string.email::CALL`, `"zod"::z.string.min::CALL`, `"zod"::z.string.max::CALL`, `"zod"::z.string.min.max::CALL` - String validation chains
- `"zod"::z.number::CALL`, `"zod"::z.number.min::CALL` - Number validation
- `"zod"::z.boolean::CALL`, `"zod"::z.literal::CALL`, `"zod"::z.union::CALL`, `"zod"::z.array::CALL`, `"zod"::z.record::CALL`, `"zod"::z.custom::CALL` - Additional type validators

**Hook Return Values:**
- `Declaration::{ execute, isPending }::CONST` - Destructured from `useServerAction`
- `Declaration::execute::CALL` - Function to trigger the server action
- `Declaration::isPending::CALL` - Boolean loading state

## Behaviors & Rules

**Server-Side Contract:**
- Files must include the `"use server"` directive at the top
- Actions are constructed via method chaining: `createServerAction().input(schema).handler(async ({ input }) => { ... })`
- The handler receives a destructured object containing `input` validated against the Zod schema
- Actions without input validation use: `createServerAction().handler(async () => { ... })`
- Errors are thrown using `new ZSAError("CODE", "message")` with specific error codes
- Handlers return plain objects, typically including `success: true` and relevant data payloads

**Error Handling Codes (Observed):**
- `"CONFLICT"` - Resource already exists (e.g., duplicate user)
- `"NOT_FOUND"` - Resource not found (e.g., invalid credentials)
- `"FORBIDDEN"` - Permission denied (e.g., insufficient team permissions)
- `"VALIDATION_ERROR"` - Input validation failure (e.g., password mismatch)
- `"INVALID_TOKEN"` - Token validation failure (e.g., expired verification)
- `"VERIFICATION_FAILED"` - Specific to passkey/WebAuthn verification failures

**Client-Side Contract:**
- `useServerAction` accepts the server action as first argument and an options object as second
- Options object supports `onError`, `onSuccess`, and `onStart` callbacks
- `onError` receives an error object with `error.message` or `error.err.message` properties
- `execute` function accepts the input shape defined by the server's Zod schema
- `isPending` tracks the async state of the action execution

**Integration Patterns:**
- Server actions are typically defined in `src/server/actions/{domain}.ts` (e.g., `auth.ts`, `team.ts`, `workflow.ts`)
- Client components using actions are often named with `_client.tsx` suffix (e.g., `sign-up_client.tsx`)
- Form integration uses `react-hook-form` with `zodResolver` to share Zod schemas between client validation and server action input
- Toast notifications via `"sonner"::toast.error::CALL`, `"sonner"::toast.success::CALL`, `"sonner"::toast.loading::CALL`, `"sonner"::toast.dismiss::CALL` are commonly used in `onError`, `onSuccess`, and `onStart` callbacks

## Inputs & Outputs

**Server Action Input:**
- Defined via `.input(zodSchema)` chain method
- Schema constants observed: `signUpSchema`, `signInSchema`, `verifyEmailSchema`, `resetPasswordSchema`, `teamInviteSchema`, `userSettingsSchema`, `forgotPasswordSchema`, `catchaSchema`
- Input fields accessed in handlers via: `input.email`, `input.password`, `input.captchaToken`, `input.firstName`, `input.lastName`, `input.token`, `input.response`, `input.challenge`, `input.itemId`, `input.itemType`, `input.selectedTeam`, `input.credentialId`

**Server Action Output:**
- Return type is a plain object, typically: `{ success: true, ...data }`
- Data payloads include: `userId`, `user`, `teamId`, `workflowId`, `projectId`, `options` (for passkey registration)
- Error output: Throws `ZSAError` instances caught by client's `onError` callback

**Client Hook Input:**
- First argument: The imported server action constant (e.g., `signUpAction`, `switchTeamAction`)
- Second argument: Configuration object with `onError`, `onSuccess`, `onStart` callbacks

**Client Hook Output:**
- `execute`: Async function matching the server's input schema
- `isPending`: Boolean indicating request in-flight status

## Dependencies

**Required:**
- `"zsa"` - Server-side action creation and error handling
- `"zsa-react"` - Client-side `useServerAction` hook
- `"zod"` - Input schema validation (shared between server and client)

**Commonly Paired With:**
- `"react-hook-form"` - Form state management with `useForm` and `zodResolver`
- `"@hookform/resolvers/zod"` - Zod resolver for react-hook-form
- `"sonner"` - Toast notifications for action feedback
- `"next/navigation"` - `useRouter`, `router.refresh`, `router.push` for navigation after actions
- `"drizzle-orm"` - Database operations within action handlers

## Code Patterns

**Basic Server Action Definition:**
```typescript
"use server";

import { createServerAction, ZSAError } from "zsa";
import { z } from "zod";

const inputSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export const signInAction = createServerAction()
  .input(inputSchema)
  .handler(async ({ input }) => {
    // input.email and input.password are type-safe
    const user = await getUserFromDB(input.email);
    if (!user) {
      throw new ZSAError("NOT_FOUND", "Invalid credentials");
    }
    return { success: true, user };
  });
```

**Server Action Without Input:**
```typescript
export const signOutAction = createServerAction()
  .handler(async () => {
    await clearSession();
    return { success: true };
  });
```

**Client-Side Consumption:**
```typescript
"use client";

import { useServerAction } from "zsa-react";
import { signInAction } from "@/server/actions/auth";
import { toast } from "sonner";

export function SignInForm() {
  const { execute: executeSignIn, isPending } = useServerAction(signInAction, {
    onError: (error) => {
      toast.error(error.message);
    },
    onSuccess: () => {
      toast.success("Signed in successfully");
    },
  });

  async function onSubmit(values: { email: string; password: string }) {
    await executeSignIn(values);
  }
}
```

**Chained Validation with Complex Schemas:**
```typescript
const createTeamSchema = z.object({
  name: z.string().min(1).max(100),
  description: z.string().max(1000).optional(),
  avatarUrl: z.string().url().max(600).optional().or(z.literal("")),
});

export const createTeamAction = createServerAction()
  .input(createTeamSchema)
  .handler(async ({ input }) => {
    // input.name, input.description, input.avatarUrl are type-safe and validated
    return { success: true, teamId: "generated-id" };
  });
```

**Error Handling with Specific Codes:**
```typescript
.handler(async ({ input }) => {
  const existingUser = await getUserFromDB(input.email);
  if (existingUser) {
    throw new ZSAError("CONFLICT", "User already exists");
  }
  
  const hasPermission = await checkTeamPermission(input.teamId);
  if (!hasPermission) {
    throw new ZSAError("FORBIDDEN", "Insufficient permissions");
  }
  
  if (input.password !== input.confirmPassword) {
    throw new ZSAError("VALIDATION_ERROR", "Passwords do not match");
  }
});
```

**Integration with React Hook Form:**
```typescript
const form = useForm<z.infer<typeof formSchema>>({
  resolver: zodResolver(formSchema),
  defaultValues: { email: "", password: "" },
});

const { execute } = useServerAction(signUpAction, {
  onError: (error) => {
    toast.error(error.err.message);
  },
});

async function onSubmit(values: z.infer<typeof formSchema>) {
  await execute(values);
}
```

**Loading State Management:**
```typescript
const { execute: saveWorkflow, isPending } = useServerAction(saveWorkflowAction, {
  onStart: () => {
    toast.loading("Saving workflow...");
  },
  onSuccess: () => {
    toast.dismiss();
    toast.success("Workflow saved");
  },
  onError: (error) => {
    toast.dismiss();
    toast.error(error.message);
  },
});
```