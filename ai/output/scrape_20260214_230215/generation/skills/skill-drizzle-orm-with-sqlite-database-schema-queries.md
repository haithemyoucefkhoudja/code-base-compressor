# Skill: Drizzle ORM with SQLite (Database Schema & Queries)

## Summary
This skill documents the usage of Drizzle ORM with SQLite for type-safe database operations in a Next.js application. It covers schema definition using `sqliteTable` with column constraints, table relations using the `relations` helper with `one()` and `many()`, type-safe queries via the `db.query` API (findFirst/findMany), mutations (insert/update/delete), and TypeScript type inference using `InferSelectModel` and `InferInsertModel`.

## Key Components
- **`sqliteTable`** (from `drizzle-orm/sqlite-core`): Core function for defining table schemas
- **`text`, `integer`**: Column type definitions for SQLite
- **`primaryKey`, `notNull`, `unique`, `references`**: Column constraints for data integrity
- **`relations`, `one`, `many`**: Utilities for defining table associations and eager loading
- **`InferSelectModel`, `InferInsertModel`**: TypeScript type inference utilities for table types
- **`db.query`**: Query builder API with `findFirst` and `findMany` methods
- **`db.insert`, `db.update`, `db.delete`**: Mutation APIs for data modification
- **`eq`, `and`, `or`, `desc`, `asc`**: Filter and ordering operators from `drizzle-orm`
- **`sql`**: Template literal tag for raw SQL expressions in updates
- **Table Constants**: `userTable`, `teamTable`, `teamMembershipTable`, `teamInvitationTable`, `projectTable`, `workflowTable`, `passKeyCredentialTable`, `creditTransactionTable`, `purchasedItemsTable`, `teamRoleTable`
- **Enum Constants**: `SYSTEM_ROLES_ENUM`, `TEAM_PERMISSIONS`, `CREDIT_TRANSACTION_TYPE`, `PURCHASABLE_ITEM_TYPE`

## Behaviors & Rules

### Schema Definition Patterns
- Tables are defined using `sqliteTable("table_name", { columns })` with column objects
- Primary keys use `text("id").primaryKey()` or `text().primaryKey().$defaultFn(() => generateId())` for auto-generation
- Foreign keys use `text("foreign_id").notNull().references(() => otherTable.id)`
- Timestamps use `integer("created_at", { mode: "timestamp" })` with `.notNull()`
- Boolean flags use `integer("is_active", { mode: "boolean" }).default(1).notNull()`
- Unique constraints use `.unique()` on column definitions
- Default values use `.default(value)` or `.$defaultFn(() => generatedValue)` for dynamic defaults

### Relations Definition Rules
- Relations are defined separately from tables using `relations(table, ({ one, many }) => ({...}))`
- One-to-many relations use `many(relatedTable)` in the parent and `one(parentTable, { fields: [fk], references: [pk] })` in the child
- The `with` option in queries enables eager loading of related data (e.g., `with: { team: true, members: true }`)

### Query Patterns
- **Single record**: `db.query.tableName.findFirst({ where: eq(column, value) })`
- **Multiple records**: `db.query.tableName.findMany({ where: eq(column, value), orderBy: [desc(column)], limit: n, offset: n })`
- **Complex filters**: Use `and(eq(col1, val1), eq(col2, val2))` for compound WHERE clauses
- **Relations loading**: Include `with: { relationName: true }` to fetch related tables in a single query
- **Column selection**: Use `columns: { id: true, email: true }` to select specific fields

### Mutation Patterns
- **Insert**: `db.insert(table).values({ ...data }).returning()` returns the inserted row
- **Update**: `db.update(table).set({ column: value }).where(eq(id, value)).returning()` modifies specific rows
- **Arithmetic updates**: Use `sql`${table.column} - ${amount}`` for column-relative updates (e.g., decrementing credits)
- **Delete**: `db.delete(table).where(eq(id, value))` removes specific rows

### Type Inference
- `InferSelectModel<typeof tableName>` generates the TypeScript type for query results
- `InferInsertModel<typeof tableName>` generates the type for insert operations
- These types are exported from schema files for use in actions and components

## Inputs & Outputs

### Schema Definition Inputs
- **Table name**: String identifier for the SQLite table
- **Column definitions**: Object with column names as keys and type constraints as values
- **Reference functions**: Callbacks to other tables for foreign key constraints

### Query Inputs
- **where**: Filter conditions using `eq`, `and`, `or` operators
- **orderBy**: Array of `desc(column)` or `asc(column)` for sorting
- **limit/offset**: Pagination parameters (numbers)
- **with**: Object specifying which relations to eager load (e.g., `{ team: true, members: true }`)
- **columns**: Object specifying which columns to select (e.g., `{ id: true, email: true }`)

### Mutation Inputs
- **values**: Object matching `InferInsertModel` for inserts
- **set**: Partial object for updates (can include `sql` expressions)
- **where**: Filter conditions identifying target rows

### Outputs
- **Query results**: Objects typed as `InferSelectModel` (or arrays thereof)
- **Insert/Update returns**: Arrays of inserted/updated rows when using `.returning()`
- **Relation data**: Nested objects when using `with` clause in queries

## Dependencies
- `drizzle-orm`: Core ORM functionality (operators, relations, type inference)
- `drizzle-orm/sqlite-core`: SQLite-specific column types and table definition
- `@libsql/client` or `better-sqlite3`: Database driver (implied by `createClient` patterns)
- TypeScript: For type inference utilities (`InferSelectModel`, `InferInsertModel`)

## Code Patterns

### Table Schema Definition
```typescript
import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";

export const userTable = sqliteTable("users", {
  id: text("id").primaryKey().$defaultFn(() => generateId()),
  email: text("email").notNull().unique(),
  firstName: text("first_name"),
  lastName: text("last_name"),
  currentCredits: integer("current_credits").default(0).notNull(),
  lastCreditRefreshAt: integer("last_credit_refresh_at", { mode: "timestamp" }),
  role: text("role", { enum: ["USER", "ADMIN"] }).default("USER").notNull(),
});

export const teamTable = sqliteTable("teams", {
  id: text("id").primaryKey(),
  slug: text("slug").notNull().unique(),
  name: text("name").notNull(),
  avatarUrl: text("avatar_url"),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull(),
});

export const teamMembershipTable = sqliteTable("team_memberships", {
  userId: text("user_id")
    .notNull()
    .references(() => userTable.id),
  teamId: text("team_id")
    .notNull()
    .references(() => teamTable.id),
  roleId: text("role_id").notNull(),
  isSystemRole: integer("is_system_role", { mode: "boolean" }).default(true).notNull(),
  joinedAt: integer("joined_at", { mode: "timestamp" }),
});
```

### Relations Definition
```typescript
import { relations } from "drizzle-orm";

export const teamRelations = relations(teamTable, ({ many }) => ({
  members: many(teamMembershipTable),
  invitations: many(teamInvitationTable),
  projects: many(projectTable),
}));

export const teamMembershipRelations = relations(teamMembershipTable, ({ one }) => ({
  user: one(userTable, {
    fields: [teamMembershipTable.userId],
    references: [userTable.id],
  }),
  team: one(teamTable, {
    fields: [teamMembershipTable.teamId],
    references: [teamTable.id],
  }),
}));

export const userRelations = relations(userTable, ({ many }) => ({
  teamMemberships: many(teamMembershipTable),
  passkeys: many(passKeyCredentialTable),
  creditTransactions: many(creditTransactionTable),
}));
```

### Type Inference Exports
```typescript
import { InferSelectModel, InferInsertModel } from "drizzle-orm";

export type User = InferSelectModel<typeof userTable>;
export type NewUser = InferInsertModel<typeof userTable>;
export type Team = InferSelectModel<typeof teamTable>;
export type TeamMembership = InferSelectModel<typeof teamMembershipTable>;
export type CreditTransaction = InferSelectModel<typeof creditTransactionTable>;
```

### Query Patterns
```typescript
import { eq, and, desc, asc } from "drizzle-orm";
import { db } from "@/db";

// Single record lookup
const user = await db.query.userTable.findFirst({
  where: eq(userTable.id, userId),
});

// Lookup with column selection
const userByEmail = await db.query.userTable.findFirst({
  where: eq(userTable.email, email),
  columns: { id: true, email: true, passwordHash: true },
});

// List with filtering, ordering, and pagination
const transactions = await db.query.creditTransactionTable.findMany({
  where: eq(creditTransactionTable.userId, userId),
  orderBy: [desc(creditTransactionTable.createdAt)],
  limit: 20,
  offset: 0,
});

// Complex compound filter
const memberships = await db.query.teamMembershipTable.findMany({
  where: and(
    eq(teamMembershipTable.teamId, teamId),
    eq(teamMembershipTable.userId, userId)
  ),
});

// Query with eager-loaded relations
const teamWithMembers = await db.query.teamTable.findFirst({
  where: eq(teamTable.id, teamId),
  with: {
    members: {
      with: {
        user: true,
      },
    },
  },
});
```

### Mutation Patterns
```typescript
import { eq, sql } from "drizzle-orm";

// Insert with returning
const [newUser] = await db.insert(userTable)
  .values({
    email: input.email,
    firstName: input.firstName,
    lastName: input.lastName,
    passwordHash: hashedPassword,
    currentCredits: 0,
    createdAt: new Date(),
  })
  .returning();

// Update specific fields
await db.update(userTable)
  .set({ 
    firstName: input.firstName,
    lastName: input.lastName,
    updatedAt: new Date(),
  })
  .where(eq(userTable.id, userId));

// Arithmetic update using sql template literal
await db.update(userTable)
  .set({ 
    currentCredits: sql`${userTable.currentCredits} - ${amount}`,
    lastCreditRefreshAt: new Date(),
  })
  .where(eq(userTable.id, userId));

// Delete with filter
await db.delete(teamInvitationTable)
  .where(eq(teamInvitationTable.id, invitationId));

// Delete with compound filter
await db.delete(teamMembershipTable)
  .where(
    and(
      eq(teamMembershipTable.teamId, teamId),
      eq(teamMembershipTable.userId, userId)
    )
  );
```

### Enum Constants Pattern
```typescript
export const SYSTEM_ROLES_ENUM = {
  OWNER: "owner",
} as const;

export const TEAM_PERMISSIONS = {
  ACCESS_DASHBOARD: "access_dashboard",
  REMOVE_MEMBERS: "remove_members",
  INVITE_MEMBERS: "invite_members",
  CREATE_COMPONENTS: "create_components",
  EDIT_COMPONENTS: "edit_components",
} as const;

export const CREDIT_TRANSACTION_TYPE = {
  MONTHLY_REFRESH: "monthly_refresh",
} as const;

export const PURCHASABLE_ITEM_TYPE = {
  COMPONENT: "component",
} as const;
```