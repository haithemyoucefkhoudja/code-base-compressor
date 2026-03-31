# Skill: Zod Schema Validation with React Hook Form

## Summary
This skill implements type-safe form validation by combining Zod for runtime schema validation with react-hook-form for form state management. The pattern uses `@hookform/resolvers/zod` to bridge the two libraries, enabling automatic validation error propagation to UI components. The system includes a custom Form component hierarchy (FormField, FormItem, FormLabel, FormControl, FormMessage, FormDescription) that integrates with react-hook-form's context providers to display validation errors and manage field state.

## Key Components

**Validation Layer:**
- `zod` - Core validation library (`"zod"::z::CALL`)
- `signUpSchema`, `signInSchema`, `forgotPasswordSchema`, `resetPasswordSchema`, `verifyEmailSchema`, `userSettingsSchema`, `teamInviteSchema` - Authentication and settings schemas (`Declaration::signUpSchema::CONST`, etc.)
- `WorkflowGraphSchema`, `ArroNodeSchema`, `ArroEdgeSchema`, `NodeRuleSchema`, `NodeCategorySchema` - Workflow/canvas data schemas (`Declaration::WorkflowGraphSchema::CONST`, etc.)
- `catchaSchema`, `passkeyEmailSchema`, `googleSSOCallbackSchema` - Specialized validation schemas (`Declaration::catchaSchema::CONST`, etc.)

**Form State Management:**
- `useForm` - Hook for form initialization (`"react-hook-form"::useForm::CALL`)
- `zodResolver` - Resolver bridge (`"@hookform/resolvers/zod"::zodResolver::CALL`)
- `useWatch` - Field watching utility (`"react-hook-form"::useWatch::CALL`)
- `ControllerProps`, `FieldValues`, `FieldPath` - TypeScript types (`"react-hook-form"::ControllerProps`, etc.)

**UI Component System (src/components/ui/form.tsx):**
- `FormField` - Wrapper connecting react-hook-form Controller to UI (`src\components\ui\form.tsx::FormField::DEF`)
- `FormItem` - Layout container with spacing (`"@/components/ui/form"::FormItem::JSX`)
- `FormLabel` - Label component with error state styling (`"@/components/ui/form"::FormLabel::JSX`)
- `FormControl` - Input wrapper with validation state (`"@/components/ui/form"::FormControl::JSX`)
- `FormMessage` - Error message display component (`"@/components/ui/form"::FormMessage::JSX`)
- `FormDescription` - Helper text component (`"@/components/ui/form"::FormDescription::JSX`)
- `useFormField` - Hook accessing field context (`Declaration::useFormField::CALL`)
- `FormFieldContext`, `FormItemContext` - React contexts for field state (`Declaration::FormFieldContext::CALL`, `Declaration::FormItemContext::CALL`)

## Behaviors & Rules

**Schema Definition Patterns:**
- String fields use chained validators: `.email()`, `.min()`, `.max()`, `.optional()` (`"zod"::z.string.email::CALL`, `"zod"::z.string.min.max::CALL`, `"zod"::z.string.optional::CALL`)
- Objects defined with `z.object()` containing typed fields (`"zod"::z.object::CALL`)
- Arrays validated with `z.array()` (`"zod"::z.array::CALL`)
- Enums created via `z.enum()` (implied by `NodeCategorySchema`)
- Union types for literal discriminated unions: `z.union([z.literal("error"), z.literal("warning"), z.literal("info")])` (`"zod"::z.union::CALL`, `"zod"::z.literal::CALL`)
- Records with defaults: `z.record(z.any()).default({})` (`"zod"::z.record.default::CALL`)
- Custom validation for complex types (WebAuthn responses): `z.custom()` (`"zod"::z.custom::CALL`)
- Refinement rules for cross-field validation (password confirmation matching) using `.refine()` with `path` targeting specific fields

**Form Initialization Rules:**
- `useForm` must receive `resolver: zodResolver(schema)` to enable Zod validation (`"@hookform/resolvers/zod"::zodResolver::CALL` + `"react-hook-form"::useForm::CALL`)
- `defaultValues` must be provided to prevent undefined controlled component warnings
- Form type inferred via `z.infer<typeof schema>`

**Validation Error Handling:**
- Errors accessed via `form.formState.errors.{field}.message` (`Declaration::form.formState.errors.captchaToken.message::CALL`)
- `FormMessage` component automatically displays error text when `error` exists in field context
- `FormLabel` applies `text-destructive` class when field has errors
- `FormControl` applies `border-destructive` and `focus-visible:ring-destructive` when errors present

**Submission Patterns:**
- Submit handler wrapped via `form.handleSubmit(onSubmit)` (`Declaration::form.handleSubmit::CALL`)
- Validated data passed to server actions via `execute` function (`Declaration::execute::CALL`)
- Results destructured as `[data, err]` tuple (`Declaration::[data, err]::CONST`)

**Field Registration:**
- All inputs must be wrapped in `FormField` with `control={form.control}` prop (`Declaration::form.control::CALL`)
- Field values updated via `form.setValue()` for programmatic updates (`Declaration::form.setValue::CALL`)
- Form reset via `form.reset()` (`Declaration::form.reset::CALL`)

## Inputs & Outputs

**Inputs:**
- **Schema**: Zod object defining field types, constraints, and error messages (`z.object()` with `.email()`, `.min()`, `.max()` chains)
- **Default Values**: Object matching schema shape for initial form state
- **Submit Handler**: `onSubmit` function receiving validated data (`Declaration::onSubmit::CONST`)
- **Server Action**: `execute` function for form submission (`Declaration::execute::CALL`)

**Outputs:**
- **Validated Data**: Type-safe object matching schema definition (inferred via `z.infer`)
- **Error Messages**: Mapped to specific fields via `form.formState.errors`
- **Form State**: `isSubmitting`, `isValid`, `isDirty`, `isLoading` boolean flags
- **Field State**: `error`, `invalid`, `isDirty`, `isTouched` per-field via `useFormField`

## Dependencies

- `zod` - Runtime validation and type inference
- `react-hook-form` - Form state management and validation orchestration
- `@hookform/resolvers/zod` - Resolver integration between Zod and react-hook-form
- `@radix-ui/react-label` - Primitive for FormLabel component (`"@radix-ui/react-label"::LabelPrimitive.Root::CALL`)
- `@radix-ui/react-slot` - Slot primitive for FormControl (`"@radix-ui/react-slot"::Slot`)
- `@/components/ui/input` - Input components used within FormControl
- `@/components/ui/button` - Submit buttons
- `@/lib/utils` - `cn()` utility for class merging

## Code Patterns

**Schema Definition with Refinement:**
```typescript
const resetPasswordSchema = z.object({
  token: z.string().min(1),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});
```

**Form Setup with Resolver:**
```typescript
const form = useForm<z.infer<typeof signUpSchema>>({
  resolver: zodResolver(signUpSchema),
  defaultValues: {
    email: "",
    firstName: "",
    lastName: "",
    password: "",
    captchaToken: "",
  },
});
```

**Form Field Registration Pattern:**
```typescript
<FormField
  control={form.control}
  name="email"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Email</FormLabel>
      <FormControl>
        <Input placeholder="you@example.com" {...field} />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

**Error Access Pattern:**
```typescript
// Accessing specific field error
form.formState.errors.captchaToken?.message

// Using useFormField hook inside components
const { error, formMessageId } = useFormField();
const body = error ? String(error?.message) : children;
```

**Server Action Integration:**
```typescript
const onSubmit = async (values: z.infer<typeof signUpSchema>) => {
  const [data, err] = await execute(values);
  if (err) {
    toast.error(err.message);
    return;
  }
  toast.success("Success");
};
```

**Complex Object Schema (Workflow):**
```typescript
const ArroNodeSchema = z.object({
  id: z.string(),
  category: NodeCategorySchema,
  tool: z.string(),
  label: z.string(),
  position: z.object({
    x: z.number(),
    y: z.number(),
  }),
  config: z.record(z.any()).default({}),
  properties: z.record(z.string()).default({}),
  rules: z.array(NodeRuleSchema).default([]),
});
```

**Form Context Provider Pattern:**
```typescript
const FormFieldContext = React.createContext({});
const FormItemContext = React.createContext({});

// Provider usage in FormField
<FormFieldContext.Provider value={{ name: props.name }}>
  <Controller {...props} />
</FormFieldContext.Provider>
```