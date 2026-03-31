# Skill: Server Actions with ZSA (Type-Safe Server Actions)

## Summary
A type-safe server action pattern for Next.js applications using the ZSA library. This pattern enables end-to-end type safety by chaining Zod schema validation with server-side handlers, providing structured error handling via `ZSAError`, and offering a React hook (`useServerAction`) for client-side execution with built-in loading states and lifecycle callbacks.

## Key Components

**Server-Side (ZSA Core):**
- `"zsa"::createServerAction::CALL` - Factory function for creating server actions (supports no-args, function, identifier, or call argument patterns)
- `"zsa"::createServerAction.input::CALL` - Method for attaching Zod validation schemas
- `"zsa"::createServerAction.handler::CALL` - Method for attaching the async handler implementation
- `"zsa"::createServerAction.input.handler::CALL` - Complete chained pattern combining input schema and handler
- `"zsa"::ZSAError::CALL` - Error constructor for throwing typed errors with error codes and messages
- `"zsa"::instanceof ZSAError::CALL` - Type guard pattern for error handling

**Client-Side (ZSA React):**
- `"zsa-react"::useServerAction::CALL` - React hook for executing server actions with automatic type inference

**Validation Layer (Zod Integration):**
- `"zod"::z.object::CALL`, `"zod"::z.string::CALL`, `"zod"::z.number::CALL`, `"zod"::z.boolean::CALL`, `"zod"::z.array::CALL`, `"zod"::z.union::CALL`, `"zod"::z.literal::CALL`, `"zod"::z.void::CALL`, `"zod"::z.custom::CALL`
- Schema refinements: `"zod"::z.string.email::CALL`, `"zod"::z.string.min::CALL`, `"zod"::z.string.max::CALL`, `"zod"::z.string.optional::CALL`, `"zod"::z.number.min::CALL`, `"zod"::z.string.min.max::CALL`, `"zod"::z.record.default::CALL`

## Behaviors & Rules

**Server Action Construction:**
- Must use `"use server"` directive at the top of action files
- `createServerAction()` returns a builder object that supports method chaining
- `.input()` accepts a Zod schema object (via `z.object()`, `z.string()`, etc.) and validates inputs before the handler executes
- `.handler()` accepts an async function that receives a destructured `{ input }` parameter containing the validated, type-safe input data
- Handler return types are automatically inferred and propagated to the client

**Error Handling:**
- `ZSAError` constructor accepts two string arguments: `(errorCode, message)` or `(errorCode, unknown)`
- Common error codes observed: `"VALIDATION_ERROR"`, `"INTERNAL_ERROR"`, `"INVALID_AMOUNT"`, `"UNAUTHORIZED"`, `"NOT_FOUND"`
- Errors must be thrown using `throw new ZSAError(...)` to trigger the error handling path
- On the client, errors must be checked using `err instanceof ZSAError` before accessing error properties

**Client-Side Execution:**
- `useServerAction()` accepts the server action as its first argument
- Optional second argument is an options object containing lifecycle callbacks: `onStart`, `onSuccess`, `onError`
- Hook returns an object with: `execute` (function to trigger the action), `isPending` (boolean loading state), `data` (returned result), and `error` (caught error)
- `execute` accepts the input shape defined by the Zod schema attached to the server action

**Input Validation Rules:**
- All inputs must pass Zod schema validation before reaching the handler
- Schema methods like `.email()`, `.min()`, `.max()`, `.optional()` can be chained on string/number schemas
- Complex inputs use `z.object()` with nested `z.string()`, `z.number()`, `z.boolean()`, `z.array()`, or `z.union()` types

## Inputs & Outputs

**Server Action Definition:**
- **Input:** Zod schema via `.input()` method
- **Handler Input:** `{ input: ValidatedSchemaType }` destructured parameter
- **Handler Output:** Any serializable object (inferred automatically)

**ZSAError Constructor:**
- **Parameters:** `(code: string, message: string | unknown)`
- **Properties:** `code` (error code string), `message` (error description)

**useServerAction Hook:**
- **Input Parameters:** 
  - `action`: The exported server action function
  - `options?: { onStart?: () => void, onSuccess?: (result) => void, onError?: (error) => void }`
- **Returns:** `{ execute: Function, isPending: boolean, data: TResult | undefined, error: Error | undefined }`

**execute Function (from hook):**
- **Input:** Object matching the Zod schema defined in `.input()`
- **Output:** Promise resolving to the handler's return type

## Dependencies

- `zsa` - Core server action library providing `createServerAction` and `ZSAError`
- `zsa-react` - React integration providing `useServerAction` hook
- `zod` - Schema validation library for input type safety
- `next` - Next.js framework (for Server Actions infrastructure)

## Code Patterns

**Basic Server Action with Input Validation:**
```typescript
"use server";

import { createServerAction, ZSAError } from "zsa";
import { z } from "zod";

const inputSchema = z.object({
  id: z.string(),
  amount: z.number().min(0),
  email: z.string().email(),
});

export const exampleAction = createServerAction()
  .input(inputSchema)
  .handler(async ({ input }) => {
    const { id, amount, email } = input;
    
    if (amount <= 0) {
      throw new ZSAError("INVALID_AMOUNT", "Amount must be positive");
    }
    
    return {
      success: true,
      data: { id, processedAmount: amount * 2 },
    };
  });
```

**Simple Server Action (No Input):**
```typescript
"use server";

import { createServerAction } from "zsa";

export const simpleAction = createServerAction(async () => {
  return { message: "Hello from server" };
});
```

**Error Handling Pattern:**
```typescript
"use server";

import { createServerAction, ZSAError } from "zsa";
import { z } from "zod";

export const errorProneAction = createServerAction()
  .input(z.object({ value: z.string().min(1) }))
  .handler(async ({ input }) => {
    if (!input.value) {
      throw new ZSAError("VALIDATION_ERROR", "Value is required");
    }
    
    try {
      return { result: input.value.toUpperCase() };
    } catch (error) {
      throw new ZSAError("INTERNAL_ERROR", "Failed to process");
    }
  });
```

**Client Component Usage:**
```typescript
"use client";

import { useServerAction } from "zsa-react";
import { exampleAction, errorProneAction } from "@/lib/actions/example";
import { ZSAError } from "zsa";

export function ExampleClientComponent() {
  const { execute, isPending, data, error } = useServerAction(exampleAction);
  
  const { execute: executeWithCallbacks } = useServerAction(errorProneAction, {
    onStart: () => {
      console.log("Action started");
    },
    onSuccess: (result) => {
      console.log("Action succeeded:", result);
    },
    onError: (error) => {
      console.error("Action failed:", error);
    },
  });
  
  const handleSubmit = async () => {
    try {
      const result = await execute({
        id: "123",
        amount: 100,
        email: "test@example.com",
      });
      
      if (result) {
        console.log("Result:", result.data);
      }
    } catch (err) {
      if (err instanceof ZSAError) {
        console.error("ZSA Error:", err.code, err.message);
      } else {
        console.error("Unknown error:", err);
      }
    }
  };
  
  return (
    <button onClick={handleSubmit} disabled={isPending}>
      {isPending ? "Loading..." : "Submit"}
    </button>
  );
}
```

**Advanced Schema Patterns:**
```typescript
const complexSchema = z.object({
  name: z.string().min(2).max(50),
  email: z.string().email().optional(),
  tags: z.array(z.string()),
  metadata: z.record(z.string()),
  status: z.union([z.literal("active"), z.literal("inactive")]),
  count: z.number().min(0).default(0),
});
```