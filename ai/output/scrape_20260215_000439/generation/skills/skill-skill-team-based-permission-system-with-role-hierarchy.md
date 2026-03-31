# Skill: Team-Based Permission System with Role Hierarchy

## Summary
A comprehensive access control system implementing multi-tenant team permissions with hierarchical roles (Owner/Admin/Member), granular permission constants (ACCESS_DASHBOARD, INVITE_MEMBERS, etc.), and server-side validation. The system supports team invitations with role assignment, membership management with permission checks, and UI components that conditionally render based on user permissions. Database relations link teams, memberships, invitations, and roles through Drizzle ORM, while server actions enforce permissions before executing privileged operations.

## Key Components
- **TEAM_PERMISSIONS**: Constant object defining granular permissions (`ACCESS_DASHBOARD`, `INVITE_MEMBERS`, `REMOVE_MEMBERS`, `CREATE_COMPONENTS`, `EDIT_COMPONENTS`)
- **SYSTEM_ROLES_ENUM**: Enum defining role hierarchy (`OWNER`, `ADMIN`, `MEMBER`)
- **hasTeamPermission**: Utility function checking if user has specific permission in team
- **requireTeamPermission**: Utility function throwing error if permission missing (for page guards)
- **hasTeamMembership**: Utility checking if user is active member of team
- **teamTable, teamMembershipTable, teamInvitationTable, teamRoleTable**: Drizzle ORM table definitions
- **teamRelations, teamMembershipRelations, teamRoleRelations, teamInvitationRelations**: Drizzle relations defining table associations
- **inviteUserAction**: Server action creating invitations with role assignment
- **acceptInvitationAction / acceptTeamInviteAction**: Server actions converting invitation to membership
- **removeTeamMemberAction**: Server action removing members with permission validation
- **getUserTeamsAction**: Server action fetching teams with user permissions
- **createTeamAction**: Server action for team creation
- **updateSelectedTeamAction**: Server action for switching active team context
- **getPendingInvitationsForCurrentUserAction**: Server action fetching pending invites
- **TeamSwitcher**: UI component for switching between teams with role display
- **InviteMemberModal**: Dialog component for inviting users with role selection
- **RemoveMemberButton**: Button component with permission checks and tooltip for disabled states
- **TeamDashboardPage**: Page component using `requireTeamPermission` for access control

## Behaviors & Rules
- **Hierarchical Roles**: `SYSTEM_ROLES_ENUM` defines `OWNER` > `ADMIN` > `MEMBER` hierarchy
- **Granular Permissions**: `TEAM_PERMISSIONS` constants define specific actions; roles aggregate these permissions
- **System vs Custom Roles**: `isSystemRole` boolean distinguishes built-in roles from custom team roles
- **Permission Validation**: Server actions check `hasTeamPermission` before executing privileged operations
- **Page Guards**: Route handlers use `requireTeamPermission` to throw 403/redirect if user lacks access
- **Owner Protection**: UI disables removal of team owners (`isDisabled={member.role === SYSTEM_ROLES_ENUM.OWNER}`)
- **Invitation Expiration**: Invitations include `expiresAt` timestamp; tokens must be valid for acceptance
- **Membership Activation**: New members join with `isActive: true` and `joinedAt` timestamp
- **Role Assignment**: Invitations specify `roleId` and `isSystemRole` flag determining permissions upon acceptance
- **Team Context**: Session includes `teams` array with user's role in each team for client-side checks
- **Database Integrity**: Relations enforce referential integrity between teams, memberships, users, and roles
- **Rate Limiting**: Email invitations use `RATE_LIMITS.EMAIL` to prevent abuse

## Inputs & Outputs
- **hasTeamPermission**: Input: `(teamSlug: string, permission: TEAM_PERMISSIONS)`; Output: `Promise<boolean>`
- **requireTeamPermission**: Input: `(teamSlug: string, permission: TEAM_PERMISSIONS)`; Output: `Promise<void>` (throws if denied)
- **inviteUserAction**: Input: `{ teamId: string, email: string, roleId: string, isSystemRole: boolean }`; Output: Invitation record with token
- **acceptInvitationAction**: Input: `string (token)`; Output: Membership record
- **removeTeamMemberAction**: Input: `{ teamId: string, userId: string }`; Output: Success confirmation
- **getUserTeamsAction**: Input: `void (uses session)`; Output: `Array<{ id, name, role, slug, avatarUrl?, permissions }>`
- **TeamSwitcher**: Input: `teams: Array<{ id, name, role, slug }>`; Output: Navigation UI with selection handlers
- **InviteMemberModal**: Input: `teamId: string, trigger: ReactNode`; Output: Dialog with form (email, role select, submit)
- **RemoveMemberButton**: Input: `{ teamId, userId, memberName, isDisabled?, tooltipText? }`; Output: Button with delete confirmation

## Dependencies
- **Drizzle ORM**: Database schema definitions (`sqliteTable`, `relations`, `eq`, `and`, `desc`)
- **Next.js Server Actions**: Async server functions with `"use server"` directive
- **ZSA (Zod Server Actions)**: `createServerAction` for type-safe action definitions with input validation
- **React Hook Form**: Form handling in `InviteMemberModal` with `zodResolver`
- **Zod**: Schema validation for team operations (`createTeamSchema`, `teamInviteSchema`)
- **Radix UI**: `Dialog`, `Select`, `Tooltip`, `Popover`, `Command` primitives for permission UI components
- **Lucide React**: Icons (`Plus`, `Trash`, `Check`, `ChevronsUpDown`, `Shield`) for team UI
- **Next.js Navigation**: `useRouter`, `redirect`, `notFound` for routing after permission checks
- **@react-email/components**: `Html`, `Body`, `Container`, `Heading`, `Text`, `Link` for invitation emails
- **date-fns**: `formatDistanceToNow` for invitation expiration display

## Code Patterns

### Permission Guard in Page Component
```typescript
export default async function TeamDashboardPage({ 
  params 
}: { 
  params: Promise<{ teamSlug: string }> 
}) {
  const { teamSlug } = await params;
  await requireTeamPermission(teamSlug, TEAM_PERMISSIONS.ACCESS_DASHBOARD);
  const team = await getTeamBySlug(teamSlug);
  if (!team) notFound();
  return <TeamDashboard team={team} />;
}
```

### Server Action with Permission Check
```typescript
export const removeTeamMemberAction = createServerAction
  .input(z.object({ teamId: z.string(), userId: z.string() }))
  .handler(async ({ input }) => {
    const hasPermission = await hasTeamPermission(input.teamId, TEAM_PERMISSIONS.REMOVE_MEMBERS);
    if (!hasPermission) throw new ZSAError("INSUFFICIENT_PERMISSIONS");
    await db.delete(teamMembershipTable)
      .where(and(
        eq(teamMembershipTable.teamId, input.teamId),
        eq(teamMembershipTable.userId, input.userId)
      ));
  });
```

### UI Component with Permission Check
```typescript
<RemoveMemberButton
  teamId={team.id}
  userId={member.userId}
  memberName={member.name}
  isDisabled={member.role === SYSTEM_ROLES_ENUM.OWNER}
  tooltipText="Cannot remove team owner"
/>
```

### Database Relations Definition
```typescript
export const teamRelations = relations(teamTable, ({ many }) => ({
  memberships: many(teamMembershipTable),
  invitations: many(teamInvitationTable),
  roles: many(teamRoleTable),
}));

export const teamMembershipRelations = relations(teamMembershipTable, ({ one }) => ({
  team: one(teamTable, { 
    fields: [teamMembershipTable.teamId], 
    references: [teamTable.id] 
  }),
  user: one(userTable, { 
    fields: [teamMembershipTable.userId], 
    references: [userTable.id] 
  }),
  role: one(teamRoleTable, { 
    fields: [teamMembershipTable.roleId], 
    references: [teamRoleTable.id] 
  }),
}));
```

### Invitation Flow with Role Assignment
```typescript
// Creating invitation
await db.insert(teamInvitationTable).values({
  teamId: input.teamId,
  email: input.email,
  roleId: input.roleId,
  isSystemRole: input.isSystemRole,
  token: generateToken(),
  expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
  invitedBy: session.userId,
});

// Accepting invitation
const invitation = await db.query.teamInvitationTable.findFirst({ 
  where: eq(teamInvitationTable.token, token) 
});
await db.insert(teamMembershipTable).values({
  teamId: invitation.teamId,
  userId: session.userId,
  roleId: invitation.roleId,
  isSystemRole: invitation.isSystemRole,
  joinedAt: new Date(),
  isActive: true,
});
await db.update(teamInvitationTable)
  .set({ acceptedAt: new Date(), updatedAt: new Date() })
  .where(eq(teamInvitationTable.id, invitation.id));
```

### Team Switcher with Role Display
```typescript
export function TeamSwitcher({ 
  teams 
}: { 
  teams: Array<{ id: string; name: string; role: string; slug: string; avatarUrl?: string }> 
}) {
  const [selectedTeam, setSelectedTeam] = useState(teams[0]);
  const router = useRouter();
  
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline">
          <Avatar className="mr-2 h-5 w-5">
            <AvatarImage src={selectedTeam?.avatarUrl} />
            <AvatarFallback>{getInitials(selectedTeam?.name)}</AvatarFallback>
          </Avatar>
          {selectedTeam?.name}
          <ChevronsUpDown className="ml-2 h-4 w-4 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-0">
        <Command>
          <CommandGroup heading="Teams">
            {teams.map((team) => (
              <CommandItem 
                key={team.id} 
                onSelect={() => {
                  setSelectedTeam(team);
                  router.push(`/dashboard/teams/${team.slug}`);
                }}
              >
                <Check className={cn(
                  "mr-2 h-4 w-4",
                  selectedTeam?.id === team.id ? "opacity-100" : "opacity-0"
                )} />
                <span className="flex-1">{team.name}</span>
                <span className="text-xs text-muted-foreground">{team.role}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
```

### Client-Side Permission Check (Session Context)
```typescript
// Check if user has specific permission in any team
const canInvite = session.teams.some(team => 
  team.id === targetTeamId && 
  team.permissions.includes(TEAM_PERMISSIONS.INVITE_MEMBERS)
);

// Check system role
const isOwner = membership.role === SYSTEM_ROLES_ENUM.OWNER;
```