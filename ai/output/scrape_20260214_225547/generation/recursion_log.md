
# LAYER 1 (Files: 7)

**Files:** `['"zsa"::createServerAction.handler::CALL', '"zsa"::createServerAction::CALL', '"zsa"::ZSAError::CALL', '"zsa-react"::useServerAction::CALL', '"zsa"::createServerAction.input::CALL', '"zsa"::instanceof ZSAError::CALL', '"zsa"::createServerAction.input.handler::CALL']`

### A) RECONSTRUCTED CODE

Based on the atlas metadata and visual patterns, the ZSA (Type-Safe Server Actions) pattern is implemented as follows:

**Pattern 1: Server Action Definition** (`"zsa"::createServerAction.input.handler::CALL`)

```typescript
// File: src/lib/actions/example.ts (inferred path)
import { createServerAction, ZSAError } from "zsa";
import { z } from "zod";

export const serverActionName = createServerAction()
  .input(z.object({
    // Zod schema definition
    fieldName: z.string(),
    fieldEmail: z.string().email(),
    // ... additional fields
  }))
  .handler(async ({ input }) => {
    // Business logic implementation
    if (errorCondition) {
      throw new ZSAError("ERROR_CODE", "Error message");
    }
    return { success: true, data: result };
  });
```

**Pattern 2: Client-Side Action Consumption** (`"zsa-react"::useServerAction::CALL`)

```typescript
// File: src/components/example-component.tsx (inferred path)
import { useServerAction } from "zsa-react";
import { serverActionName } from "@/lib/actions/example";

export function ExampleComponent() {
  const { 
    execute, 
    isPending, 
    data, 
    error 
  } = useServerAction(serverActionName, {
    onStart: () => {
      // Optional: Handle action start
    },
    onSuccess: (data) => {
      // Optional: Handle successful execution
      console.log("Success:", data);
    },
    onError: (error) => {
      // Optional: Handle error
      if (error instanceof ZSAError) {
        console.error("ZSA Error:", error.message);
      }
    }
  });

  const handleSubmit = async (formData: FormData) => {
    await execute(formData);
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Form implementation */}
      <button disabled={isPending}>Submit</button>
      {error && <div>Error: {error.message}</div>}
    </form>
  );
}
```

**Pattern 3: Error Instantiation** (`"zsa"::ZSAError::CALL`)

```typescript
import { ZSAError } from "zsa";

// Error creation pattern (98 instances with string-string signature)
throw new ZSAError("INVALID_INPUT", "Invalid email format");
throw new ZSAError("UNAUTHORIZED", "User not authenticated");
throw new ZSAError("NOT_FOUND", "Resource not found");
```

**Pattern 4: Error Type Checking** (`"zsa"::instanceof ZSAError::CALL`)

```typescript
import { ZSAError } from "zsa";

// Type guard pattern (13 instances)
if (error instanceof ZSAError) {
  // Handle ZSA-specific error
  const errorCode = error.code;
  const errorMessage = error.message;
}
```

**Pattern 5: Chained Input Schema** (`"zsa"::createServerAction.input::CALL`)

```typescript
import { createServerAction } from "zsa";
import { z } from "zod";

// Input schema definition pattern (35 variations)
export const actionWithInput = createServerAction()
  .input(z.object({
    id: z.string().uuid(),
    amount: z.number().positive(),
  }));
```

### B) NEXT

The following concrete action implementations are referenced in the mission but not fully decoded in the current atlas. Their specific business logic, input schemas, and file locations are required to complete the skill documentation:

- `signInAction`
- `signUpAction`
- `createTeamAction`
- `inviteUserAction`
- `purchaseAction`
- `z` (Zod schema definitions - referenced by `.input()` calls)

### C) TOOL OUTPUT

The current atlas shows the ZSA library interface patterns (createServerAction, useServerAction, ZSAError) but lacks the concrete action implementations that demonstrate the actual usage patterns with specific Zod schemas and business logic. The specific actions mentioned in the mission (`signInAction`, `signUpAction`, `createTeamAction`, `inviteUserAction`, `purchaseAction`) are not visible in the provided stitched regions.

**Status:** SEARCH_CONTINUE

---

# LAYER 2 (Files: 23)

**Files:** `['Declaration::input.response.id::CALL', 'Declaration::getUserTeamsAction::CONST', 'src\\components\\purchase-button.tsx::PurchaseButton::DEF', 'Declaration::input.itemType::CALL', 'Declaration::input.email::CALL', 'Declaration::input.firstName::CALL', 'Declaration::input.response::CALL', 'Declaration::input.lastName::CALL', 'Declaration::input.password::CALL', 'Declaration::signInAction::CONST', 'Declaration::signUpAction::CONST', 'Declaration::input.token::CALL', 'Declaration::input::CALL', 'Declaration::input.selectedTeam::CALL', 'Declaration::getUsersAction::CONST', '"@/components/ui/input"::Input::JSX', 'Declaration::createTeamAction::CONST', 'Declaration::input.captchaToken::CALL', 'Declaration::input.challenge::CALL', 'Declaration::purchaseAction::CONST', 'Declaration::inviteUserAction::CONST', 'Declaration::input.credentialId::CALL', 'Declaration::input.itemId::CALL']`

### A) RECONSTRUCTED CODE

Based on the atlas metadata and visible declarations, the following code artifacts are reconstructed:

```typescript
// File: src/components/purchase-button.tsx
// Component: PurchaseButton
// Status: DEFINITION VISIBLE (PROPS: itemId, itemType)
interface PurchaseButtonProps {
  itemId: string;
  itemType: string;
}

export function PurchaseButton({ itemId, itemType }: PurchaseButtonProps): import("react").JSX.Element {
  // PLACEHOLDER: Implementation uses useServerAction(purchaseAction) per pattern
  // PLACEHOLDER: JSX content not fully readable in atlas
  return <>{/* JSX implementation */}</>;
}
```

```typescript
// File: @/components/ui/input
// Component: Input (JSX Primitive)
// Props derived from atlas shapes:
interface InputProps {
  type?: string;
  className?: string;
  placeholder?: string;
  disabled?: boolean | unknown;
  value?: unknown;
  onChange?: (event: unknown) => void;
  onKeyDown?: (event: unknown) => void | unknown;
  autoFocus?: boolean;
  id?: string;
  ref?: React.Ref<HTMLInputElement>;
  "data-sidebar"?: string;
}

export function Input(props: InputProps): JSX.Element {
  // PLACEHOLDER: Implementation not visible in atlas
  return <input {...props} />;
}
```

```typescript
// Server Action Declarations (CONST sites visible, implementations collapsed)
// Pattern: ZSA (Type-Safe Server Actions)

// Declaration: signInAction
// Referenced Inputs: input.email, input.password, input.token, input.captchaToken
export const signInAction = /* PLACEHOLDER: createServerAction().input().handler() chain not visible */;

// Declaration: signUpAction  
// Referenced Inputs: input.email, input.password, input.firstName, input.lastName
export const signUpAction = /* PLACEHOLDER: createServerAction().input().handler() chain not visible */;

// Declaration: createTeamAction
// Referenced Inputs: input.name, input.slug (inferred from pattern)
export const createTeamAction = /* PLACEHOLDER: createServerAction().input().handler() chain not visible */;

// Declaration: inviteUserAction
// Referenced Inputs: input.email, input.teamId (inferred)
export const inviteUserAction = /* PLACEHOLDER: createServerAction().input().handler() chain not visible */;

// Declaration: purchaseAction
// Referenced Inputs: input.itemId, input.itemType, input.selectedTeam
export const purchaseAction = /* PLACEHOLDER: createServerAction().input().handler() chain not visible */;

// Declaration: getUserTeamsAction
export const getUserTeamsAction = /* PLACEHOLDER: createServerAction().input().handler() chain not visible */;

// Declaration: getUsersAction
export const getUsersAction = /* PLACEHOLDER: createServerAction().input().handler() chain not visible */;

// Input Field Accessors (CALL sites visible within handlers/components):
// - input.email
// - input.token  
// - input.captchaToken
// - input.selectedTeam
// - input.password
// - input.response
// - input.response.id
// - input.itemType
// - input.itemId
// - input.firstName
// - input.lastName
// - input.challenge
// - input.credentialId
```

### B) NEXT (MISSING ELEMENTS)

The following critical elements are referenced but not fully visible in the current atlas:

1. `createServerAction` - The core factory function from "zsa" package (import and usage)
2. `useServerAction` - The React hook from "zsa-react" for client-side consumption
3. `ZSAError` - Error handling class from "zsa"
4. `.input()` method chains - Zod schema definitions for each server action
5. `.handler()` method chains - Implementation logic for each server action
6. Full implementation of `signInAction` (beyond CONST declaration)
7. Full implementation of `purchaseAction` (beyond CONST declaration)
8. Full implementation of `signUpAction` (beyond CONST declaration)
9. Full implementation of `createTeamAction` (beyond CONST declaration)
10. Full implementation of `inviteUserAction` (beyond CONST declaration)

### C) TOOL OUTPUT

The current atlas shows the **CONST declarations** of server actions and **CALL sites** for input fields, but the actual **`.input()` and `.handler()` chain implementations** are collapsed or not visible. To complete the skill reconstruction, I need to see the actual server action definitions with their Zod schemas and handler implementations.

**Status:** SEARCH_CONTINUE

---

# LAYER 3 (Files: 2)

**Files:** `['"@xyflow/react"::Handle::JSX', 'Declaration::handleSave::CONST']`

### A) RECONSTRUCTED CODE

Based on the atlas decoding and metadata provided:

**File: `components/flow/handle-usage.tsx` (inferred location)**
```tsx
import { Handle, Position } from "@xyflow/react";

// "@xyflow/react"::Handle::JSX usage pattern
export function FlowNodeWithHandles() {
  return (
    <div className="node-container">
      <Handle 
        type="target" 
        position={Position.Left} 
        className="handle-target"
      />
      {/* Node content region */}
      <Handle 
        type="source" 
        position={Position.Right} 
        className="handle-source"
      />
    </div>
  );
}
```

**File: `actions/save-action.ts` (inferred location)**
```typescript
import { createServerAction } from "zsa";
import { z } from "zod";
// VOCAB_MISSING: ZSAError - referenced in mission but not visible in atlas

// Declaration::handleSave::CONST
// NOTE: Internal schema and handler implementation are collapsed/abstracted in atlas
export const handleSave = createServerAction()
  .input(/* SCHEMA_NOT_VISIBLE: Zod schema for save input */)
  .handler(async ({ input }) => {
    // IMPLEMENTATION_NOT_VISIBLE: save logic, ZSAError handling
    throw new Error("Implementation not visible in atlas");
  });
```

### B) NEXT (MISSING ELEMENTS)

The following internal code elements are required to complete the reconstruction but are not visible in the provided atlas:

1. `handleSave` - Full implementation including `.input()` schema definition and `.handler()` internal logic
2. `SaveInputSchema` (or equivalent) - The Zod schema passed to `.input()` 
3. `ZSAError` - Error handling class usage within the handler (referenced in mission context)

### C) TOOL OUTPUT

The atlas shows `Declaration::handleSave::CONST` as a collapsed region without visible internal structure for the `.input()` and `.handler()` chains. The implementation details, Zod schema, and error handling logic are required to complete the skill documentation.

**Status:** SEARCH_CONTINUE

---
