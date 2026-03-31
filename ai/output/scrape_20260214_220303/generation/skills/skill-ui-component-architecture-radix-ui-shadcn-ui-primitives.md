# Skill: UI Component Architecture (Radix UI + shadcn/ui primitives)

## Summary
This skill defines a component architecture pattern that wraps Radix UI uncontrolled primitives with type-safe React wrappers, applying Tailwind CSS styling via the `cn()` utility and `class-variance-authority` (cva) for variant management. The pattern creates accessible, composable UI components (Sheet, Dialog, DropdownMenu, Select, etc.) that support uncontrolled usage by default, controlled state via `open`/`onOpenChange`, CSS-based animations via data attributes, and polymorphic rendering via the Slot primitive. Components are implemented using `React.forwardRef` for ref forwarding and follow a consistent naming convention of exporting both the component and its variant configuration.

## Key Components

**Primitive Wrappers (Radix UI)**
- `"@radix-ui/react-dialog"`::`SheetPrimitive.Root`, `SheetPrimitive.Overlay`, `SheetPrimitive.Content`, `SheetPrimitive.Title`, `SheetPrimitive.Description`, `SheetPrimitive.Close`, `SheetPrimitive.Trigger`, `SheetPrimitive.Portal`
- `"@radix-ui/react-dialog"`::`DialogPrimitive.Title`, `DialogPrimitive.Description`, `DialogPrimitive.Content`, `DialogPrimitive.Overlay`, `DialogPrimitive.Close`
- `"@radix-ui/react-dropdown-menu"`::`DropdownMenuPrimitive.Content`, `DropdownMenuPrimitive.Label`, `DropdownMenuPrimitive.Item`, `DropdownMenuPrimitive.Separator`, `DropdownMenuPrimitive.Portal`, `DropdownMenuPrimitive.CheckboxItem`, `DropdownMenuPrimitive.RadioItem`, `DropdownMenuPrimitive.SubContent`, `DropdownMenuPrimitive.SubTrigger`, `DropdownMenuPrimitive.ItemIndicator`
- `"@radix-ui/react-select"`::`SelectPrimitive.Trigger`, `SelectPrimitive.Content`, `SelectPrimitive.Item`, `SelectPrimitive.Separator`, `SelectPrimitive.Viewport`, `SelectPrimitive.ScrollUpButton`, `SelectPrimitive.ScrollDownButton`, `SelectPrimitive.ItemText`, `SelectPrimitive.ItemIndicator`, `SelectPrimitive.Label`, `SelectPrimitive.Icon`, `SelectPrimitive.Portal`
- `"@radix-ui/react-avatar"`::`AvatarPrimitive.Root`, `AvatarPrimitive.Image`, `AvatarPrimitive.Fallback`
- `"@radix-ui/react-separator"`::`SeparatorPrimitive.Root`, `SeparatorPrimitive`
- `"@radix-ui/react-label"`::`LabelPrimitive.Root`, `LabelPrimitive`
- `"@radix-ui/react-accordion"`::`AccordionPrimitive.Item`, `AccordionPrimitive.Trigger`, `AccordionPrimitive.Content`, `AccordionPrimitive.Header`
- `"@radix-ui/react-tabs"`::`TabsPrimitive.List`, `TabsPrimitive.Trigger`, `TabsPrimitive.Content`
- `"@radix-ui/react-scroll-area"`::`ScrollAreaPrimitive.Root`, `ScrollAreaPrimitive.Viewport`, `ScrollAreaPrimitive.ScrollAreaScrollbar`
- `"@radix-ui/react-slot"`::`Slot`
- `"@radix-ui/react-tooltip"`::`TooltipPrimitive.Content`, `TooltipPrimitive`
- `"@radix-ui/react-context-menu"`::`ContextMenuPrimitive.Content`, `ContextMenuPrimitive.Item`, `ContextMenuPrimitive.Separator`, `ContextMenuPrimitive.Portal`, `ContextMenuPrimitive.Label`, `ContextMenuPrimitive.SubContent`, `ContextMenuPrimitive.SubTrigger`, `ContextMenuPrimitive.ItemIndicator`, `ContextMenuPrimitive.CheckboxItem`, `ContextMenuPrimitive.RadioItem`

**Styling Utilities**
- `"@/lib/utils"`::`cn` - Class name merging utility combining `clsx` and `tailwind-merge`
- `"class-variance-authority"`::`cva` - Variant definition function for component styling
- `"class-variance-authority"`::`VariantProps` - Type helper for extracting variant prop types

**Component Definitions**
- `src\components\ui\sheet.tsx`::`Sheet`, `SheetContent`, `SheetHeader`, `SheetFooter`, `SheetTitle`, `SheetDescription`, `SheetOverlay`, `SheetTrigger`, `SheetClose`, `SheetPortal`
- `src\components\ui\dialog.tsx`::`DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription`
- `src\components\ui\dropdown-menu.tsx`::`DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuLabel`, `DropdownMenuSeparator`, `DropdownMenuShortcut`, `DropdownMenuTrigger`
- `src\components\ui\select.tsx`::`Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue`
- `src\components\ui\badge.tsx`::`Badge`, `badgeVariants`
- `src\components\ui\spinner.tsx`::`Spinner`, `spinnerVariants`
- `src\components\ui\skeleton.tsx`::`Skeleton`
- `src\components\ui\breadcrumb.tsx`::`BreadcrumbEllipsis`, `BreadcrumbSeparator`
- `src\components\ui\form.tsx`::`FormField`
- `src\components\ui\context-menu.tsx`::`ContextMenuShortcut`
- `src\components\ui\avatar.tsx`::`Avatar`, `AvatarFallback`, `AvatarImage`
- `src\components\ui\separator.tsx`::`Separator`
- `src\components\ui\label.tsx`::`Label`
- `src\components\ui\button.tsx`::`Button`, `buttonVariants`
- `src\components\ui\card.tsx`::`Card`, `CardTitle`, `CardDescription`, `CardContent`, `CardHeader`, `CardFooter`
- `src\components\ui\table.tsx`::`Table`, `TableBody`, `TableCell`, `TableHead`, `TableHeader`, `TableRow`
- `src\components\ui\tabs.tsx`::`Tabs`, `TabsList`, `TabsContent`, `TabsTrigger`
- `src\components\ui\scroll-area.tsx`::`ScrollArea`
- `src\components\ui\tooltip.tsx`::`Tooltip`, `TooltipContent`, `TooltipProvider`, `TooltipTrigger`
- `src\components\ui\input.tsx`::`Input`
- `src\components\ui\textarea.tsx`::`Textarea`

## Behaviors & Rules

**Primitive Composition Pattern**
- Components are created by re-exporting Radix primitives (e.g., `const Sheet = SheetPrimitive.Root`) and wrapping sub-components with styling
- All interactive components use `React.forwardRef` to forward refs to the underlying DOM element or Radix primitive
- Components must accept a `className` prop and merge it with base styles using `cn(baseClasses, className)`

**Variant Management**
- Style variants are defined using `cva()` with explicit variant keys (e.g., `variant: "default" | "secondary" | "destructive" | "outline"` for badges, `size: "default" | "sm" | "lg"` for spinners)
- Component props extend `VariantProps<typeof variantConfig>` to expose variant options as props
- Default variants are specified in the cva configuration (e.g., `defaultVariants: { variant: "default", size: "default" }`)

**Animation & State Handling**
- Components use Radix's `data-[state=open]` and `data-[state=closed]` attributes for CSS-based animations
- Animation classes include: `animate-in`, `animate-out`, `fade-in-0`, `fade-out-0`, `zoom-in-95`, `zoom-out-95`, `slide-in-from-top-2`, `slide-out-to-bottom`
- Sheet variants include directional animations: `slide-in-from-right`, `slide-out-to-right`, `slide-in-from-left`, `slide-out-to-left`, `slide-in-from-top`, `slide-out-to-top`

**Accessibility & Keyboard Navigation**
- Inherits full accessibility features from Radix primitives (keyboard navigation, focus trapping, aria attributes)
- Dialogs and Sheets use `SheetPrimitive.Portal`/`DialogPrimitive.Portal` for rendering outside the DOM hierarchy
- Focus management is handled automatically by the underlying Radix primitive

**Polymorphism**
- Components support polymorphic rendering via the `Slot` primitive (e.g., `asChild` prop pattern)
- `displayName` is explicitly set on all forwardedRef components for debugging (e.g., `SheetTitle.displayName = SheetPrimitive.Title.displayName`)

**Form Integration**
- Form components use `react-hook-form` Controller pattern (e.g., `FormField` wraps `Controller`)
- Form inputs support standard HTML form attributes and ref forwarding

## Inputs & Outputs

**Common Props Interface**
```typescript
// Standard component props pattern observed
interface ComponentProps extends React.HTMLAttributes<HTMLElement> {
  className?: string;
  asChild?: boolean; // For Slot-based polymorphism
  variant?: VariantProps<typeof cvaConfig>["variant"];
  size?: VariantProps<typeof cvaConfig>["size"];
}

// Sheet specific
interface SheetContentProps extends React.ComponentPropsWithoutRef<typeof SheetPrimitive.Content> {
  side?: "top" | "bottom" | "left" | "right";
}

// Select specific
interface SelectProps extends React.ComponentPropsWithoutRef<typeof SelectPrimitive.Root> {
  // Inherits value, defaultValue, onValueChange, open, onOpenChange
}

// Badge/Spinner specific
interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}
interface SpinnerProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof spinnerVariants> {
  show?: boolean;
}
```

**Return Types**
- All components return `React.JSX.Element` or `React.ReactNode`
- forwardRef components return `React.ElementRef<typeof Primitive.Component>`
- `cn()` utility returns `string` (merged class names)

## Dependencies

**Core Libraries**
- `"@radix-ui/react-dialog"` - Base for Sheet and Dialog components
- `"@radix-ui/react-dropdown-menu"` - Dropdown menu functionality
- `"@radix-ui/react-select"` - Select dropdown primitive
- `"@radix-ui/react-slot"` - Polymorphic component support
- `"@radix-ui/react-avatar"` - Avatar image handling
- `"@radix-ui/react-separator"` - Visual separator primitive
- `"@radix-ui/react-label"` - Form label primitive
- `"@radix-ui/react-accordion"` - Collapsible content sections
- `"@radix-ui/react-tabs"` - Tabbed interface primitive
- `"@radix-ui/react-scroll-area"` - Custom scrollable area
- `"@radix-ui/react-tooltip"` - Tooltip positioning
- `"@radix-ui/react-context-menu"` - Right-click context menus
- `"class-variance-authority"` - Type-safe variant definitions
- `"clsx"` - Conditional class name construction (implied by cn usage)
- `"tailwind-merge"` - Tailwind class deduplication (implied by cn usage)
- `"react-hook-form"` - Form state management (for Form components)
- `"lucide-react"` - Icon components (ChevronRight, MoreHorizontal, etc.)

**Internal Utilities**
- `"@/lib/utils"`::`cn` - Required by all UI components for className merging

## Code Patterns

**1. Primitive Wrapping with Styling**
```typescript
const SheetContent = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Content>,
  SheetContentProps
>(({ className, children, side = "right", ...props }, ref) => (
  <SheetPortal>
    <SheetOverlay />
    <SheetPrimitive.Content
      ref={ref}
      className={cn(sheetVariants({ side }), className)}
      {...props}
    >
      {children}
    </SheetPrimitive.Content>
  </SheetPortal>
))
SheetContent.displayName = SheetPrimitive.Content.displayName
```

**2. Variant Definition Pattern**
```typescript
const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)
```

**3. ForwardRef Component with Slot Support**
```typescript
const SidebarMenuButton = React.forwardRef<HTMLButtonElement, SidebarMenuButtonProps>(
  ({ asChild = false, isActive = false, variant = "default", size = "default", tooltip, className, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    // ... implementation with Tooltip wrapper
    return (
      <Comp
        ref={ref}
        data-sidebar="menu-button"
        data-size={size}
        data-active={isActive}
        className={cn(sidebarMenuButtonVariants({ variant, size }), className)}
        {...props}
      />
    )
  }
)
SidebarMenuButton.displayName = "SidebarMenuButton"
```

**4. Animation State Classes**
```typescript
// Sheet overlay with fade animation
const SheetOverlay = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof SheetPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <SheetPrimitive.Overlay
    className={cn(
      "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
    ref={ref}
  />
))
```

**5. Form Field Pattern with react-hook-form**
```typescript
const FormField = <
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>
>({
  ...props
}: ControllerProps<TFieldValues, TName>) => {
  return (
    <FormFieldContext.Provider value={{ name: props.name }}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  )
}
```

**6. Breadcrumb Separator Pattern**
```typescript
const BreadcrumbSeparator = React.forwardRef<
  HTMLLIElement,
  React.HTMLAttributes<HTMLLIElement>
>(({ children, className, ...props }, ref) => (
  <li
    ref={ref}
    role="presentation"
    aria-hidden="true"
    className={cn("text-muted-foreground", className)}
    {...props}
  >
    {children ?? <ChevronRight className="h-4 w-4" />}
  </li>
))
BreadcrumbSeparator.displayName = "BreadcrumbSeparator"
```

**7. Skeleton Loading State**
```typescript
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted/50", className)}
      {...props}
    />
  )
}
Skeleton.displayName = "Skeleton"
```