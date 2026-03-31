# Skill: Drizzle ORM SQLite Database Schema and Query Management

## Summary
This skill defines a type-safe database layer using Drizzle ORM with SQLite (specifically Cloudflare D1), implementing table schemas with relations, a singleton database accessor, and dual query APIs (Query Builder for relational data and SQL Builder for raw operations). It covers nine core tables (user, team, project, workflow, credit transactions, passkey credentials, team memberships, invitations, and purchased items) with strict foreign key constraints, timestamp handling, and JSON column support.

## Key Components
- **`drizzle-orm/sqlite-core`**: `sqliteTable`, `text`, `integer`, `real`, `blob`, `index`, `primaryKey`
- **`drizzle-orm`**: `relations`, `one`, `many`, `eq`, `and`, `or`, `sql`, `desc`, `asc`, `isNull`, `gt`, `lt`, `count`
- **Database Singleton**: `getDB()` (returns D1-bound drizzle instance with schema)
- **Table Schemas**: `userTable`, `teamTable`, `projectTable`, `workflowTable`, `creditTransactionTable`, `passKeyCredentialTable`, `teamMembershipTable`, `teamInvitationTable`, `purchasedItemsTable`
- **ID Generation**: `@paralleldrive/cuid2`::`createId` (used with `$defaultFn`)
- **Query APIs**: `db.query.[table].findFirst`, `db.query.[table].findMany`, `db.select`, `db.insert`, `db.update`, `db.delete`

## Behaviors & Rules
- **Primary Key Pattern**: All tables use `text("id").primaryKey()` with `$defaultFn(createId).notNull()` for auto-generated CUID2 IDs
- **Foreign Key Constraints**: References use `.references(() => targetTable.id)` with `notNull()` on required relationships (e.g., `teamMembershipTable.teamId`)
- **Timestamp Handling**: Uses `integer("created_at", { mode: "timestamp" })` with `.default(sql\`CURRENT_TIMESTAMP\`)` for automatic timestamping
- **Boolean Storage**: Stored as `integer("field", { mode: "boolean" }).default(0)` (SQLite lacks native boolean)
- **JSON Columns**: JSON data stored via `text("transports", { mode: "json" })` (e.g., passkey transports array)
- **Unique Constraints**: Applied via `.unique()` chain (e.g., `teamTable.slug`, `userTable.email`, `passKeyCredentialTable.credentialId`)
- **Index Definitions**: Secondary indexes defined in table config callback: `(table) => ({ idx: index("name").on(table.column) })`
- **Relations Definition**: Strict one-to-many (`many()`) and many-to-one (`one()`) via `relations()` helper with explicit field/references mapping
- **Query Builder Behavior**: Supports nested relation loading via `with: { relationName: true }` or `with: { relationName: { with: { nested: true } } }`
- **SQL Builder Behavior**: Methods chain strictly: `db.select().from().where().orderBy().limit()`
- **Returning Clause**: Insert and update operations use `.returning()` to fetch affected rows (e.g., `db.insert(table).values({}).returning()`)
- **Credit Balance Logic**: `real` type used for monetary/credit values with default `0`
- **Soft References**: Some fields like `projectTable.ownerUserId` use `.references()` without `notNull()` allowing nullable ownership

## Inputs & Outputs
- **Schema Inputs**: Column definitions (type, constraints, defaults), index configurations, relation mappings
- **Query Inputs**: 
  - Filters: `eq(column, value)`, `and(condition, condition)`, `sql\`expression\``
  - Options: `{ where, orderBy: [desc(column)], limit, offset, with: relations }`
  - Values: Objects matching table schema for insert/update
- **Outputs**:
  - Query results: Array of table rows or single row (undefined if not found for `findFirst`)
  - Mutations: Array of returned rows from `.returning()`
  - Count queries: `[{ count: number }]`

## Dependencies
- `drizzle-orm` (core operators and relations)
- `drizzle-orm/sqlite-core` (SQLite-specific column types)
- `@paralleldrive/cuid2` (ID generation via `createId`)
- `@opennextjs/cloudflare` (implied by `getCloudflareContext` for D1 binding access)
- Environment: `process.env.DB` (D1 database binding)

## Code Patterns

**Table Definition with Indexes:**
```typescript
export const projectTable = sqliteTable("projects", {
  id: text("id").primaryKey().$defaultFn(createId).notNull(),
  ownerUserId: text("owner_user_id").references(() => userTable.id),
  teamId: text("team_id").references(() => teamTable.id),
  name: text("name").notNull(),
  graphJson: text("graph_json"),
  createdAt: integer("created_at", { mode: "timestamp" }).default(sql`CURRENT_TIMESTAMP`),
}, (table) => ({
  teamIdIdx: index("project_team_id_idx").on(table.teamId),
}));
```

**Relations Definition:**
```typescript
export const teamRelations = relations(teamTable, ({ many }) => ({
  memberships: many(teamMembershipTable),
  invitations: many(teamInvitationTable),
  projects: many(projectTable),
}));

export const teamMembershipRelations = relations(teamMembershipTable, ({ one }) => ({
  team: one(teamTable, {
    fields: [teamMembershipTable.teamId],
    references: [teamTable.id],
  }),
  user: one(userTable, {
    fields: [teamMembershipTable.userId],
    references: [userTable.id],
  }),
}));
```

**Database Singleton:**
```typescript
import { drizzle } from "drizzle-orm/d1";
import * as schema from "./schema";

let db: ReturnType<typeof drizzle<typeof schema>> | null = null;

export function getDB() {
  if (!db) {
    db = drizzle(process.env.DB as any, { schema });
  }
  return db;
}
```

**Query Builder Pattern (with nested relations):**
```typescript
const team = await db.query.teamTable.findFirst({
  where: eq(teamTable.id, teamId),
  with: {
    memberships: {
      with: {
        user: {
          columns: { id: true, email: true, firstName: true, lastName: true },
        },
      },
    },
  },
});

const transactions = await db.query.creditTransactionTable.findMany({
  where: and(
    eq(creditTransactionTable.userId, userId),
    sql`${creditTransactionTable.remainingAmount} > 0`
  ),
  orderBy: [desc(creditTransactionTable.createdAt)],
  limit: 10,
});
```

**SQL Builder Pattern (CRUD):**
```typescript
// Select specific columns
const userEmails = await db
  .select({ id: userTable.id, email: userTable.email })
  .from(userTable)
  .where(eq(userTable.email, "user@example.com"));

// Insert with returning
const [newTeam] = await db
  .insert(teamTable)
  .values({ name: "Team Name", slug: "team-slug" })
  .returning();

// Update with calculation
await db
  .update(userTable)
  .set({
    currentCredits: sql`${userTable.currentCredits} - ${amount}`,
    updatedAt: new Date(),
  })
  .where(eq(userTable.id, userId))
  .returning();

// Delete with compound where
await db
  .delete(teamMembershipTable)
  .where(and(
    eq(teamMembershipTable.teamId, teamId),
    eq(teamMembershipTable.userId, userId)
  ));
```