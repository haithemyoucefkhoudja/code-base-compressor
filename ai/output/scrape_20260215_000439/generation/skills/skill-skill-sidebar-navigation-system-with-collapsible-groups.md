# Skill: Sidebar Navigation System with Collapsible Groups

## Summary
A comprehensive sidebar navigation system built on shadcn/ui primitives, featuring collapsible nested navigation groups, team/project switching via dropdown menus, responsive mobile drawer behavior, and Zustand-based state management. The system integrates Radix UI Collapsible primitives for expand/collapse functionality, uses Sheet components for mobile responsiveness, and implements active route highlighting with Next.js routing integration.

## Key Components

**Core Sidebar Container:**
- `Sidebar` - Main container component with `collapsible` prop support (`"icon" | "offcanvas" | "none"`)
- `SidebarProvider` - Context provider managing sidebar open/closed state
- `SidebarInset` - Content area wrapper that adjusts based on sidebar state
- `SidebarHeader` - Top section for branding/team switcher
- `SidebarContent` - Scrollable navigation content area
- `SidebarFooter` - Bottom section for user profile/actions
- `SidebarRail` - Collapsed mode indicator rail

**Navigation Menu System:**
- `NavMain` - Primary navigation component rendering `SidebarMenu` with collapsible groups
- `NavUser` - User profile section with avatar, name, email, and sign-out action
- `NavProjects` - Project list navigation using `SidebarMenu` primitives
- `TeamSwitcher` - Team/project selection dropdown using `Select` or `DropdownMenu` primitives

**Menu Primitives (from @/components/ui/sidebar):**
- `SidebarMenu` - Navigation list container (`<nav>` element)
- `SidebarMenuItem` - Individual menu item wrapper with `collapsible` prop support
- `SidebarMenuButton` - Interactive button with active state styling (`isActive` prop)
- `SidebarMenuAction` - Secondary action button within menu items
- `SidebarMenuBadge` - Notification badge for menu items
- `SidebarMenuSub` - Sub-menu container for nested items
- `SidebarMenuSubItem` - Nested menu item
- `SidebarMenuSubButton` - Button for nested navigation links

**Group Organization:**
- `SidebarGroup` - Logical grouping of navigation items
- `SidebarGroupLabel` - Section label for groups
- `SidebarGroupContent` - Content container within groups
- `SidebarGroupAction` - Action button for group headers
- `SidebarSeparator` - Visual divider between sections
- `SidebarInput` - Search/filter input for sidebar

**Collapsible System:**
- `Collapsible` (from `@radix-ui/react-collapsible`) - Primitive for expand/collapse
- `CollapsibleTrigger` - Toggle button for collapsible sections
- `CollapsibleContent` - Animated content container

**Mobile Responsiveness:**
- `Sheet` (from `@/components/ui/sheet`) - Mobile drawer container
- `SheetContent` - Drawer content with `side` prop (`"left"` for sidebar)
- `SheetTrigger` - Mobile menu trigger button
- `useIsMobile` - Hook detecting mobile viewport (`MOBILE_BREAKPOINT = 768`)

**State Management:**
- `useNavStore` - Zustand store for navigation state (active team, menu open/closed)
- `useSidebar` - Hook accessing `SidebarContext` (open state, toggle function)
- `SidebarContext` - React context providing sidebar state and toggle methods

**Layout Integration:**
- `AppSidebar` - Composite component assembling all sidebar pieces
- `NavFooterLayout` - Layout wrapper with navigation and footer
- `BaseLayout` - Root layout with ThemeProvider and sidebar structure

## Behaviors & Rules

**Collapsible Navigation Groups:**
- Navigation items with `items` array property render as collapsible groups using `Collapsible` primitive
- Groups default to expanded state unless explicitly controlled
- `CollapsibleTrigger` wraps the parent `SidebarMenuButton` to toggle visibility
- `CollapsibleContent` animates height changes with CSS transitions
- Nested depth supported via recursive `SidebarMenuSub` structures

**Active State Management:**
- `SidebarMenuButton` accepts `isActive` boolean prop for visual highlighting
- Active state determined by current pathname matching item URL (via `usePathname`)
- Active styling uses `data-active` attribute or explicit `isActive` class variants
- Sub-menu items can independently show active states

**Team/Project Switching:**
- `TeamSwitcher` renders within `SidebarHeader` or `SidebarMenu`
- Uses `Select` or `DropdownMenu` primitives for team selection dropdown
- Zustand store (`useNavStore`) persists active team selection
- Team list populated via `teams` prop with `id`, `name`, `logo`, `role` properties
- Switching teams triggers navigation to team-specific routes (`/dashboard/teams/${team.slug}`)

**Responsive Behavior:**
- Desktop: Sidebar renders as fixed or sticky sidebar with `SidebarRail` for collapsed state
- Mobile (`< 768px`): Sidebar renders inside `Sheet` component as slide-out drawer
- `useIsMobile` hook monitors viewport width to conditionally render mobile vs desktop layouts
- Mobile sidebar closes automatically on route navigation

**State Persistence:**
- Sidebar open/closed state managed via Zustand (`useNavStore`) or local React state
- `toggleSidebar` function flips open state boolean
- `setOpen` allows explicit state control
- State persists across route changes but not page reloads (unless persisted to storage)

**User Profile Integration:**
- `NavUser` displays user avatar (`Avatar` component), name, and email
- Sign-out action via `useSignOut` hook
- Renders within `SidebarFooter` as `SidebarMenu` with single `SidebarMenuItem`
- Avatar shows initials fallback when image unavailable (via `getInitials` utility)

**Icon and Label Handling:**
- Menu items accept `icon` property as Lucide icon component
- Icons render at `h-4 w-4` or `h-5 w-5` size within buttons
- Labels truncate with `truncate` class to prevent overflow
- Collapsed mode shows icons only, hiding labels

**Permission-Based Rendering:**
- Navigation items can be conditionally rendered based on team permissions
- `hasTeamPermission` utility checks user permissions before rendering restricted items
- `requireTeamPermission` used for server-side access control

## Inputs & Outputs

**NavMain Component:**
- **Input:** `items: NavItem[]` - Array of navigation items with `title`, `url`, `icon`, `isActive`, and optional `items` (for nested groups)
- **Output:** Rendered `SidebarMenu` with collapsible groups and active state styling

**TeamSwitcher Component:**
- **Input:** `teams: Team[]` - Array with `id`, `name`, `logo` (React component), `role`, `slug`
- **Output:** Dropdown UI with team selection, active team highlighting, and navigation trigger

**NavUser Component:**
- **Input:** User session data (via `useSessionStore`) - `firstName`, `lastName`, `email`, `avatar`
- **Output:** User profile card with avatar, name, email, and sign-out action

**SidebarMenuButton:**
- **Input:** `isActive?: boolean`, `asChild?: boolean`, `tooltip?: string`, `size?: "default" | "sm" | "lg"`
- **Output:** Styled button or link with active state classes and tooltip support

**Collapsible Groups:**
- **Input:** `open?: boolean`, `onOpenChange?: (open: boolean) => void`, `defaultOpen?: boolean`
- **Output:** Animated expand/collapse container with trigger button

## Dependencies

**Core Libraries:**
- `zustand` - State management for navigation store (`create`, `combine` middleware)
- `@radix-ui/react-collapsible` - Primitive collapsible functionality (`CollapsiblePrimitive.Root`, `CollapsiblePrimitive.Trigger`, `CollapsiblePrimitive.Content`)
- `@radix-ui/react-dialog` - Sheet primitive for mobile sidebar (`DialogPrimitive.Root`, `DialogPrimitive.Overlay`, `DialogPrimitive.Content`)
- `@radix-ui/react-dropdown-menu` - Team switcher dropdowns (`DropdownMenuPrimitive.Root`, `DropdownMenuPrimitive.Trigger`, `DropdownMenuPrimitive.Content`)
- `@radix-ui/react-avatar` - User profile avatars (`AvatarPrimitive.Root`, `AvatarPrimitive.Image`, `AvatarPrimitive.Fallback`)
- `@radix-ui/react-slot` - Component composition primitive (`Slot`)

**UI Utilities:**
- `class-variance-authority` (cva) - Variant management for button/badge styling
- `clsx` - Conditional class name construction
- `tailwind-merge` - Tailwind class deduplication (via `cn` utility)
- `lucide-react` - Icon components (`Users`, `ChevronRight`, `ChevronLeft`, `Shield`, `Box`, etc.)

**Framework Integration:**
- `next/navigation` - `usePathname` for active route detection
- `next-themes` - Theme provider integration for dark mode support
- `react-hook-form` - Form handling within sidebar dialogs (implied by `useWatch` usage)

**Internal Dependencies:**
- `@/lib/utils` - `cn()` class merging utility
- `@/state/nav` - Zustand navigation store (`useNavStore`)
- `@/state/session` - Session store for user data (`useSessionStore`)
- `@/hooks/useSignOut` - Sign out functionality
- `@/hooks/useMediaQuery` or `@/hooks/useIsMobile` - Responsive breakpoint detection

## Code Patterns

**Sidebar Structure Pattern:**
```typescript
// Composite sidebar assembly in AppSidebar
<Sidebar>
  <SidebarHeader>
    <TeamSwitcher teams={teams} />
  </SidebarHeader>
  <SidebarContent>
    <NavMain items={navigationItems} />
    <NavProjects projects={projects} />
  </SidebarContent>
  <SidebarFooter>
    <NavUser />
  </SidebarFooter>
  <SidebarRail />
</Sidebar>
```

**Collapsible Navigation Item Pattern:**
```typescript
// NavMain implementation with collapsible groups
<SidebarMenu>
  {items.map((item) => (
    <Collapsible key={item.title} defaultOpen={item.isActive}>
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton isActive={item.isActive}>
            {item.icon && <item.icon />}
            <span>{item.title}</span>
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarMenuSub>
            {item.items?.map((subItem) => (
              <SidebarMenuSubItem key={subItem.title}>
                <SidebarMenuSubButton asChild>
                  <a href={subItem.url}>{subItem.title}</a>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  ))}
</SidebarMenu>
```

**Zustand Navigation Store Pattern:**
```typescript
// State management for navigation
import { create } from 'zustand';
import { combine } from 'zustand/middleware';

export const useNavStore = create(
  combine(
    { 
      activeTeam: null as Team | null,
      isOpen: true 
    },
    (set) => ({
      setActiveTeam: (team: Team) => set({ activeTeam: team }),
      toggle: () => set((state) => ({ isOpen: !state.isOpen })),
      setIsOpen: (isOpen: boolean) => set({ isOpen }),
    })
  )
);
```

**Active State Detection Pattern:**
```typescript
// Using Next.js pathname for active states
const pathname = usePathname();
const isActiveLink = (href: string) => pathname === href || pathname.startsWith(href + '/');
```

**Mobile Responsive Pattern:**
```typescript
// Conditional rendering based on mobile breakpoint
const isMobile = useIsMobile();

{isMobile ? (
  <Sheet open={open} onOpenChange={setOpen}>
    <SheetTrigger />
    <SheetContent side="left">
      <SidebarContent>{children}</SidebarContent>
    </SheetContent>
  </Sheet>
) : (
  <Sidebar>{children}</Sidebar>
)}
```

**Team Switcher Pattern:**
```typescript
// Team selection with Zustand state
const { activeTeam, setActiveTeam } = useNavStore();
const router = useRouter();

const handleTeamSelect = (team: Team) => {
  setActiveTeam(team);
  router.push(`/dashboard/teams/${team.slug}`);
};
```

**User Profile Pattern:**
```typescript
// NavUser with avatar and sign out
const { user } = useSessionStore();
const { signOut } = useSignOut();

<SidebarMenu>
  <SidebarMenuItem>
    <SidebarMenuButton size="lg" className="md:h-8 md:p-0">
      <Avatar>
        <AvatarImage src={user.avatar} alt={user.firstName} />
        <AvatarFallback>{getInitials(user.firstName + ' ' + user.lastName)}</AvatarFallback>
      </Avatar>
      <div className="grid flex-1 text-left text-sm">
        <span className="truncate font-semibold">{user.firstName} {user.lastName}</span>
        <span className="truncate text-xs">{user.email}</span>
      </div>
    </SidebarMenuButton>
  </SidebarMenuItem>
</SidebarMenu>
```

**Variant Styling Pattern:**
```typescript
// Using cva for sidebar button variants
const sidebarMenuButtonVariants = cva(
  "peer/menu-button flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-left text-sm outline-none ring-sidebar-ring transition-[width,height,padding] hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 active:bg-sidebar-accent active:text-sidebar-accent-foreground disabled:pointer-events-none disabled:opacity-50 group-has-[[data-sidebar=menu-action]]/menu-item:pr-8 aria-disabled:pointer-events-none aria-disabled:opacity-50 data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium data-[active=true]:text-sidebar-accent-foreground data-[state=open]:hover:bg-sidebar-accent data-[state=open]:hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:!size-8 group-data-[collapsible=icon]:!p-2 [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        outline: "bg-background shadow-[0_0_0_1px_hsl(var(--sidebar-border))] hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:shadow-[0_0_0_1px_hsl(var(--sidebar-accent))]",
      },
      size: {
        default: "h-8 text-sm",
        sm: "h-7 text-xs",
        lg: "h-12 text-sm group-data-[collapsible=icon]:!p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);
```