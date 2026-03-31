# Skill: shadcn/ui Component System with Radix Primitives

## Summary
A comprehensive UI component architecture that wraps Radix UI primitives with Tailwind CSS styling, providing type-safe, accessible, and composable React components. The system uses `class-variance-authority` (cva) for variant management, a custom `cn()` utility for class merging, and follows strict forwardRef patterns for component composition. It integrates with `react-hook-form` for form handling and `next-themes` for dark mode support, establishing a consistent design system across the application.

## Key Components

**Radix Primitives (Base Layer):**
- `"@radix-ui/react-dialog"`::SheetPrimitive.Root/Overlay/Content/Title/Description/Trigger/Close/Portal
- `"@radix-ui/react-select"`::SelectPrimitive.Trigger/Content/Viewport/Item/ItemText/ItemIndicator/ScrollUpButton/ScrollDownButton/Separator/Label/Icon/Portal
- `"@radix-ui/react-dropdown-menu"`::DropdownMenuPrimitive.Content/Item/ItemIndicator/SubTrigger/SubContent/Label/Separator/CheckboxItem/RadioItem/Portal
- `"@radix-ui/react-context-menu"`::ContextMenuPrimitive.Content/Item/ItemIndicator/SubTrigger/SubContent/Label/Separator/CheckboxItem/RadioItem/Portal
- `"@radix-ui/react-avatar"`::AvatarPrimitive.Root/Image/Fallback
- `"@radix-ui/react-label"`::LabelPrimitive.Root
- `"@radix-ui/react-separator"`::SeparatorPrimitive.Root
- `"@radix-ui/react-scroll-area"`::ScrollAreaPrimitive.Root/Viewport/ScrollAreaScrollbar
- `"@radix-ui/react-tabs"`::TabsPrimitive.Trigger/Content/List
- `"@radix-ui/react-collapsible"`::CollapsiblePrimitive
- `"@radix-ui/react-accordion"`::AccordionPrimitive.Item/Header/Trigger/Content
- `"@radix-ui/react-tooltip"`::TooltipPrimitive.Content
- `"@radix-ui/react-slot"`::Slot

**shadcn/ui Components (Implementation Layer):**
- `src\components\ui\sheet.tsx`::Sheet/SheetTrigger/SheetClose/SheetContent/SheetHeader/SheetFooter/SheetTitle/SheetDescription/SheetOverlay/SheetPortal
- `src\components\ui\dialog.tsx`::Dialog/DialogTrigger/DialogContent/DialogHeader/DialogFooter/DialogTitle/DialogDescription/DialogOverlay/DialogPortal/DialogClose
- `src\components\ui\form.tsx`::Form/FormField/FormItem/FormLabel/FormControl/FormDescription/FormMessage
- `src\components\ui\select.tsx`::Select/SelectGroup/SelectValue/SelectTrigger/SelectContent/SelectLabel/SelectItem/SelectSeparator/SelectScrollUpButton/SelectScrollDownButton
- `src\components\ui\dropdown-menu.tsx`::DropdownMenu/DropdownMenuTrigger/DropdownMenuContent/DropdownMenuItem/DropdownMenuCheckboxItem/DropdownMenuRadioItem/DropdownMenuLabel/DropdownMenuSeparator/DropdownMenuShortcut/DropdownMenuGroup/DropdownMenuPortal/DropdownMenuSub/DropdownMenuSubContent/DropdownMenuSubTrigger/DropdownMenuRadioGroup
- `src\components\ui\context-menu.tsx`::ContextMenu/ContextMenuTrigger/ContextMenuContent/ContextMenuItem/ContextMenuCheckboxItem/ContextMenuRadioItem/ContextMenuLabel/ContextMenuSeparator/ContextMenuShortcut/ContextMenuGroup/ContextMenuPortal/ContextMenuSub/ContextMenuSubContent/ContextMenuSubTrigger/ContextMenuRadioGroup
- `src\components\ui\breadcrumb.tsx`::Breadcrumb/BreadcrumbList/BreadcrumbItem/BreadcrumbLink/BreadcrumbPage/BreadcrumbSeparator/BreadcrumbEllipsis
- `src\components\ui\badge.tsx`::Badge
- `src\components\ui\skeleton.tsx`::Skeleton
- `src\components\ui\spinner.tsx`::Spinner
- `src\components\ui\sonner.tsx`::Toaster
- `src\components\ui\avatar.tsx`::Avatar/AvatarImage/AvatarFallback
- `src\components\ui\button.tsx`::Button
- `src\components\ui\card.tsx`::Card/CardHeader/CardTitle/CardDescription/CardContent/CardFooter
- `src\components\ui\input.tsx`::Input
- `src\components\ui\label.tsx`::Label
- `src\components\ui\separator.tsx`::Separator
- `src\components\ui\scroll-area.tsx`::ScrollArea/ScrollBar
- `src\components\ui\tabs.tsx`::Tabs/TabsList/TabsTrigger/TabsContent
- `src\components\ui\table.tsx`::Table/TableHeader/TableBody/TableRow/TableHead/TableCell
- `src\components\ui\tooltip.tsx`::Tooltip/TooltipContent/TooltipTrigger/TooltipProvider
- `src\components\ui\sidebar.tsx`::Sidebar/SidebarProvider/SidebarTrigger/SidebarContent/SidebarHeader/SidebarFooter/SidebarGroup/SidebarGroupLabel/SidebarMenu/SidebarMenuItem/SidebarMenuButton/SidebarRail/SidebarInset
- `src\components\ui\collapsible.tsx`::Collapsible/CollapsibleTrigger/CollapsibleContent
- `src\components\ui\accordion.tsx`::Accordion/AccordionItem/AccordionTrigger/AccordionContent

**Utility Functions:**
- `"@/lib/utils"`::cn
- `"class-variance-authority"`::cva
- `"clsx"`::ClassValue

## Behaviors & Rules

**Primitive Wrapping Pattern:**
- All shadcn components directly export Radix primitives (e.g., `const Sheet = SheetPrimitive.Root`, `const SheetTrigger = SheetPrimitive.Trigger`)
- Primitive components are re-exported with display names preserved for debugging
- Portal components are always used for overlay content (SheetPortal, DialogPortal, SelectPrimitive.Portal)

**Variant Management with cva:**
- All styled components use `cva` (class-variance-authority) for type-safe Tailwind variant definitions
- Variants include `defaultVariants` for fallback states
- Common variant patterns: `variant` (default, secondary, destructive, outline), `size` (sm, md, lg), `side` (top, bottom, left, right for Sheet)
- Variant props are exposed via `VariantProps<typeof componentVariants>` interface

**Class Merging Rules:**
- Universal use of `cn()` utility combining `clsx` (conditional classes) and `tailwind-merge` (conflict resolution)
- Pattern: `className={cn("base-classes", className)}` allows consumer overrides
- Animation classes use data attributes: `data-[state=open]:animate-in`, `data-[state=closed]:animate-out`, `data-[state=closed]:fade-out-0`, `data-[state=open]:fade-in-0`

**Ref Forwarding Requirements:**
- All interactive components use `React.forwardRef` with explicit typing: `React.ElementRef<typeof Primitive.Component>` and `React.ComponentPropsWithoutRef<typeof Primitive.Component>`
- `displayName` is explicitly set to match the primitive name (e.g., `SheetOverlay.displayName = SheetPrimitive.Overlay.displayName`)

**Form Integration:**
- Form components integrate with `react-hook-form` via `FormProvider`, `Controller`, and `useFormContext`
- `FormFieldContext` and `FormItemContext` provide field state to child components
- `useFormField` hook extracts field state and generates IDs for accessibility (`formItemId`, `formDescriptionId`, `formMessageId`)
- FormControl uses Radix `Slot` to pass props to child inputs
- Error states automatically apply `text-destructive` classes to labels

**Accessibility & ARIA:**
- Components inherit Radix accessibility features (keyboard navigation, focus management, ARIA attributes)
- Form items generate unique IDs using `React.useId()` for `htmlFor` and `aria-describedby` linking
- Icons include `<span className="sr-only">` for screen readers (e.g., "Close" text for X icon)
- Breadcrumb components use `aria-label="breadcrumb"` and `aria-current="page"`

**Animation States:**
- Overlay components use `data-[state=open]` and `data-[state=closed]` attributes for enter/exit animations
- Sheet variants include directional slide animations: `slide-in-from-right`, `slide-out-to-right`, etc.
- Duration classes: `data-[state=closed]:duration-300`, `data-[state=open]:duration-500`

**Composition Patterns:**
- Components are split into atomic parts (Trigger, Content, Header, Footer, Title, Description)
- Compound component pattern: `<Sheet><SheetTrigger /><SheetContent>...</SheetContent></Sheet>`
- `asChild` prop support via Radix Slot for polymorphic components (BreadcrumbLink, SelectTrigger)

**Theming Integration:**
- Components use semantic color tokens: `bg-background`, `text-foreground`, `border-border`, `text-muted-foreground`, `bg-accent`, `text-destructive`
- Sonner Toaster integrates with `next-themes` via `useTheme` hook, passing theme to toast notifications
- Dark mode support via CSS variables consumed by Tailwind classes

## Inputs & Outputs

**Props Interface Pattern:**
```typescript
// Standard component props extend HTML attributes and variant props
interface ComponentProps extends 
  React.ComponentPropsWithoutRef<typeof Primitive.Root>, 
  VariantProps<typeof componentVariants> {
  asChild?: boolean  // For Slot-based composition
  inset?: boolean   // For dropdown/menu indentation
  side?: "top" | "bottom" | "left" | "right"  // For Sheet positioning
  sideOffset?: number  // For positioning offset
}
```

**Form Field Input:**
- `name: string` - Field identifier for react-hook-form
- `control: Control` - Form control object
- `render: ({ field, fieldState, formState }) => ReactElement` - Render function

**Styling Input:**
- `className?: string` - Consumer-provided classes merged via `cn()`
- Variant props determined by cva definition (e.g., `variant`, `size`)

**Output Structure:**
- Returns `React.forwardRef` wrapped component with proper TypeScript types
- Exports both the component and its variants constant (e.g., `export { Badge, badgeVariants }`)
- Compound components exported as named exports for destructured imports

## Dependencies

**Core Primitives:**
- `@radix-ui/react-dialog` (Sheet, Dialog)
- `@radix-ui/react-select`
- `@radix-ui/react-dropdown-menu`
- `@radix-ui/react-context-menu`
- `@radix-ui/react-avatar`
- `@radix-ui/react-label`
- `@radix-ui/react-separator`
- `@radix-ui/react-scroll-area`
- `@radix-ui/react-tabs`
- `@radix-ui/react-collapsible`
- `@radix-ui/react-accordion`
- `@radix-ui/react-tooltip`
- `@radix-ui/react-slot`

**Styling & Utilities:**
- `class-variance-authority` (cva, VariantProps)
- `clsx` (conditional class joining)
- `tailwind-merge` (class conflict resolution)
- `lucide-react` (icons: X, ChevronRight, ChevronDown, Check, Circle, Loader2, etc.)

**Form Handling:**
- `react-hook-form` (FormProvider, Controller, useFormContext, useForm)
- `@hookform/resolvers/zod` (zodResolver for validation)

**Theming:**
- `next-themes` (ThemeProvider, useTheme)

**Animation:**
- `tailwindcss-animate` (animate-in, animate-out, fade-in, zoom-in, slide-in classes)

## Code Patterns

**1. Primitive Wrapper with Variants (Sheet/Dialog Pattern):**
```typescript
import * as React from "react"
import * as SheetPrimitive from "@radix-ui/react-dialog"
import { cva, type VariantProps } from "class-variance-authority"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

const Sheet = SheetPrimitive.Root
const SheetTrigger = SheetPrimitive.Trigger
const SheetClose = SheetPrimitive.Close
const SheetPortal = SheetPrimitive.Portal

const sheetVariants = cva(
  "fixed z-50 gap-4 bg-background p-6 shadow-lg transition ease-in-out data-[state=open]:animate-in data-[state=closed]:animate-out",
  {
    variants: {
      side: {
        top: "inset-x-0 top-0 border-b data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top",
        bottom: "inset-x-0 bottom-0 border-t data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
        left: "inset-y-0 left-0 h-full w-3/4 border-r data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left sm:max-w-sm",
        right: "inset-y-0 right-0 h-full w-3/4 border-l data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right sm:max-w-sm",
      },
    },
    defaultVariants: { side: "right" },
  }
)

interface SheetContentProps extends React.ComponentPropsWithoutRef<typeof SheetPrimitive.Content>, VariantProps<typeof sheetVariants> {}

const SheetContent = React.forwardRef<React.ElementRef<typeof SheetPrimitive.Content>, SheetContentProps>(({ side = "right", className, children, ...props }, ref) => (
  <SheetPortal>
    <SheetOverlay />
    <SheetPrimitive.Content ref={ref} className={cn(sheetVariants({ side }), className)} {...props}>
      {children}
      <SheetPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-secondary">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </SheetPrimitive.Close>
    </SheetPrimitive.Content>
  </SheetPortal>
))
SheetContent.displayName = SheetPrimitive.Content.displayName
```

**2. Form System with Context:**
```typescript
const FormFieldContext = React.createContext({})
const FormItemContext = React.createContext({})

const FormField = ({ ...props }) => (
  <FormFieldContext.Provider value={{ name: props.name }}>
    <Controller {...props} />
  </FormFieldContext.Provider>
)

const useFormField = () => {
  const fieldContext = React.useContext(FormFieldContext)
  const itemContext = React.useContext(FormItemContext)
  const { getFieldState, formState } = useFormContext()
  const fieldState = getFieldState(fieldContext.name, formState)
  const { id } = itemContext
  
  return {
    id,
    name: fieldContext.name,
    formItemId: `${id}-form-item`,
    formDescriptionId: `${id}-form-item-description`,
    formMessageId: `${id}-form-item-message`,
    ...fieldState,
  }
}

const FormItem = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => {
  const id = React.useId()
  return (
    <FormItemContext.Provider value={{ id }}>
      <div ref={ref} className={cn("space-y-2", className)} {...props} />
    </FormItemContext.Provider>
  )
})

const FormControl = React.forwardRef<React.ElementRef<typeof Slot>, React.ComponentPropsWithoutRef<typeof Slot>>(({ ...props }, ref) => {
  const { error, formItemId, formDescriptionId, formMessageId } = useFormField()
  return (
    <Slot
      ref={ref}
      id={formItemId}
      aria-describedby={!error ? `${formDescriptionId}` : `${formDescriptionId} ${formMessageId}`}
      aria-invalid={!!error}
      {...props}
    />
  )
})
```

**3. Simple Styled Component with cva (Badge):**
```typescript
import { cva, type VariantProps } from "class-variance-authority"

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
    defaultVariants: { variant: "default" },
  }
)

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}
```

**4. Menu System with Checkbox/Radio Items:**
```typescript
const DropdownMenuCheckboxItem = React.forwardRef<React.ElementRef<typeof DropdownMenuPrimitive.CheckboxItem>, React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.CheckboxItem>>(({ className, children, checked, ...props }, ref) => (
  <DropdownMenuPrimitive.CheckboxItem
    ref={ref}
    className={cn(
      "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className
    )}
    checked={checked}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <DropdownMenuPrimitive.ItemIndicator>
        <Check className="h-4 w-4" />
      </DropdownMenuPrimitive.ItemIndicator>
    </span>
    {children}
  </DropdownMenuPrimitive.CheckboxItem>
))
```

**5. Breadcrumb with Slot Composition:**
```typescript
import { Slot } from "@radix-ui/react-slot"

const BreadcrumbLink = React.forwardRef<HTMLAnchorElement, React.ComponentPropsWithoutRef<"a"> & { asChild?: boolean }>(({ asChild, className, ...props }, ref) => {
  const Comp = asChild ? Slot : "a"
  return <Comp ref={ref} className={cn("transition-colors hover:text-foreground", className)} {...props} />
})
```

**6. Themed Sonner Toaster:**
```typescript
"use client"
import { useTheme } from "next-themes"
import { Toaster as Sonner } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()
  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast: "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  )
}
```

**7. Utility Function (cn):**
```typescript
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```