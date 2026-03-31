# Skill: Drizzle ORM with SQLite (Database Schema & Queries)

## Summary
This skill defines database schemas using Drizzle ORM's SQLite core dialect, establishing table structures with typed columns (text, integer, real), relations between entities (one-to-many, many-to-one), and executing type-safe queries through both the relational query builder (`db.query`) and the SQL-like builder (`db.select/insert/update/delete`). The implementation uses a singleton `getDB()` pattern initialized with D1 bindings, supporting complex join queries via the `relations` API and handling timestamps, booleans, and JSON fields through SQLite-specific column modes.

## Key Components

**Schema Definition (drizzle-orm/sqlite-core):**
- `sqliteTable` - Table factory function for defining table schemas
- `text` - String column type (supports `{ length: number }`, `{ mode: "json" }`)
- `integer` - Numeric column type (supports `{ mode: "boolean" }`, `{ mode: "timestamp" }`)
- `real` - Floating-point column type (used for currency/credits)
- `blob` - Binary data column type
- `primaryKey()` - Column modifier for primary key designation
- `notNull()` - Column modifier for non-nullable constraints
- `unique()` - Column modifier for unique constraints
- `references()` - Foreign key reference modifier (e.g., `.references(() => userTable.id)`)
- `default()` - Default value modifier (accepts primitives or `sql` templates)
- `$defaultFn()` - Dynamic default value generator (e.g., `$defaultFn(createId)`)
- `index()` - Table index definition helper with `.on()` method

**Relations (drizzle-orm):**
- `relations()` - Factory for defining table relationships
- `one()` - Defines one-to-one or many-to-one relations with `fields` and `references` mapping
- `many()` - Defines one-to-many relations

**Query Operators (drizzle-orm):**
- `eq` - Equality comparison operator
- `and` - Logical AND combiner for multiple conditions
- `or` - Logical OR combiner
- `gt` / `lt` - Greater-than / Less-than operators
- `isNull` - Null check operator
- `desc` / `asc` - Ordering direction helpers
- `sql` - Template literal for raw SQL fragments
- `count` - Aggregation function

**Query Builders:**
- `db.query.[table].findFirst()` - Query single record with optional `where` and `with` (relations)
- `db.query.[table].findMany()` - Query multiple records with `where`, `orderBy`, `limit`, `offset`, and `with`
- `db.select()` / `db.select({ ... })` - SQL SELECT builder with column selection
- `db.insert().values().returning()` - SQL INSERT with return data
- `db.update().set().where().returning()` - SQL UPDATE with conditions and return data
- `db.delete().where()` - SQL DELETE with conditions

**Database Access:**
- `getDB()` - Singleton factory function returning the drizzle database instance
- `drizzle()` - Initialization function from `drizzle-orm/d1` (configured with `{ schema }`)

## Behaviors & Rules

**ID Generation Pattern:**
- Primary keys use `text("id").primaryKey().$defaultFn(createId).notNull()` where `createId` is imported from `@paralleldrive/cuid2`
- All tables use CUID2 for identifier generation via the `$defaultFn` modifier

**Timestamp Handling:**
- Timestamps stored as `integer("created_at", { mode: "timestamp" })`
- Default values set using `default(sql\`CURRENT_TIMESTAMP\`)` from `drizzle-orm`
- UpdatedAt fields follow the same pattern with manual updates on record modification

**Boolean Representation:**
- Booleans stored as `integer("is_active", { mode: "boolean" })` with default values like `default(1)` or `default(0)`

**JSON Storage:**
- JSON data stored via `text("transports", { mode: "json" })` (e.g., for WebAuthn transports array)

**Foreign Key Constraints:**
- Foreign keys defined as `text("user_id").notNull().references(() => userTable.id)`
- Nullable foreign keys omit the `notNull()` modifier (e.g., `ownerUserId` on projectTable)

**Index Definitions:**
- Indexes defined in table configuration callback: `(table) => ({ teamIdIdx: index("project_team_id_idx").on(table.teamId) })`

**Query Execution Patterns:**
- Relational queries use `db.query.tableName.findFirst({ where: eq(table.column, value) })` for single records
- Relational queries use `db.query.tableName.findMany({ where: and(...), orderBy: [desc(table.column)], limit: 10 })` for lists
- The `with` property in queries auto-joins related tables (e.g., `with: { team: true, user: true }`)
- Raw SQL builder requires `.from(table)` after `.select()`
- Insert and Update operations chain `.returning()` to retrieve the modified row(s)

**Relation Navigation:**
- One-to-many relations defined as `relations(table, ({ many }) => ({ items: many(relatedTable) }))`
- Many-to-one relations defined with explicit field mapping: `one(relatedTable, { fields: [table.foreignKey], references: [relatedTable.id] })`

**Type Safety:**
- Tables export their types via `InferSelectModel<typeof tableName>` from `drizzle-orm`
- Query results are fully typed based on schema definitions including selected columns and joined relations

## Inputs & Outputs

**Schema Definition Inputs:**
- Column names as string literals (e.g., `"id"`, `"email"`, `"created_at"`)
- Column configuration objects (e.g., `{ mode: "timestamp" }`, `{ mode: "boolean" }`, `{ mode: "json" }`)
- Default value generators (functions like `createId` or SQL templates)

**Query Inputs:**
- `where` clauses: Operator expressions (`eq`, `and`, `or`, `gt`, `lt`, `isNull`)
- `orderBy` arrays: Direction helpers (`asc`, `desc`) wrapping column references
- Pagination: `limit` (number) and `offset` (number) parameters
- Relation selection: `with` object containing boolean flags or nested relation objects
- Insert/Update data: Partial objects matching table schema types

**Outputs:**
- `findFirst` returns `Promise<Record | undefined>` including selected columns and joined relations
- `findMany` returns `Promise<Record[]>` array of results
- `insert().returning()` returns `Promise<Record[]>` (array of inserted rows)
- `update().returning()` returns `Promise<Record[]>` (array of updated rows)
- `select()` returns typed arrays based on the selection object shape

## Dependencies

**Core ORM:**
- `drizzle-orm` - Provides query operators, relations helpers, and type utilities
- `drizzle-orm/sqlite-core` - Provides SQLite-specific table and column definitions
- `drizzle-orm/d1` - Provides the `drizzle()` initialization function for Cloudflare D1 bindings

**ID Generation:**
- `@paralleldrive/cuid2` - Provides `createId` function for CUID2 generation via `init()` or direct import

**Environment:**
- `process.env.DB` - D1 database binding passed to drizzle initialization

## Code Patterns

**Table Definition with Primary Key and Timestamps:**
```typescript
import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";
import { createId } from "@paralleldrive/cuid2";

export const userTable = sqliteTable("users", {
  id: text("id").primaryKey().$defaultFn(createId).notNull(),
  email: text("email").notNull().unique(),
  firstName: text("first_name"),
  lastName: text("last_name"),
  currentCredits: real("current_credits").default(0),
  emailVerified: integer("email_verified", { mode: "boolean" }),
  createdAt: integer("created_at", { mode: "timestamp" }).default(sql`CURRENT_TIMESTAMP`),
  updatedAt: integer("updated_at", { mode: "timestamp" }).default(sql`CURRENT_TIMESTAMP`),
});
```

**Foreign Key References and Indexes:**
```typescript
export const projectTable = sqliteTable("projects", {
  id: text("id").primaryKey().$defaultFn(createId).notNull(),
  ownerUserId: text("owner_user_id").references(() => userTable.id),
  teamId: text("team_id").notNull().references(() => teamTable.id),
  name: text("name").notNull(),
  graphJson: text("graph_json"),
  createdAt: integer("created_at", { mode: "timestamp" }).default(sql`CURRENT_TIMESTAMP`),
}, (table) => ({
  teamIdIdx: index("project_team_id_idx").on(table.teamId),
}));
```

**Relations Definition:**
```typescript
import { relations } from "drizzle-orm";

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

**Database Singleton Initialization:**
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

**Relational Query with Joins:**
```typescript
const db = getDB();

// Find user with team memberships and nested team data
const user = await db.query.userTable.findFirst({
  where: eq(userTable.id, "user_id"),
  with: {
    teamMemberships: {
      with: {
        team: true,
      },
    },
  },
});

// Find many with filtering, ordering, and pagination
const transactions = await db.query.creditTransactionTable.findMany({
  where: and(
    eq(creditTransactionTable.userId, "user_id"),
    gt(creditTransactionTable.remainingAmount, 0)
  ),
  orderBy: [desc(creditTransactionTable.createdAt)],
  limit: 10,
  offset: 0,
});
```

**SQL Builder Patterns:**
```typescript
// Select specific columns
const userEmails = await db
  .select({
    id: userTable.id,
    email: userTable.email,
    currentCredits: userTable.currentCredits,
  })
  .from(userTable)
  .where(eq(userTable.email, "user@example.com"));

// Insert with returning
const [newTeam] = await db
  .insert(teamTable)
  .values({
    name: "Team Name",
    slug: "team-slug",
    creditBalance: 0,
  })
  .returning();

// Update with calculation and returning
const [updatedUser] = await db
  .update(userTable)
  .set({
    currentCredits: sql`${userTable.currentCredits} - ${amount}`,
    updatedAt: new Date(),
  })
  .where(eq(userTable.id, "user_id"))
  .returning();

// Delete with compound where
await db
  .delete(teamMembershipTable)
  .where(
    and(
      eq(teamMembershipTable.teamId, "team_id"),
      eq(teamMembershipTable.userId, "user_id")
    )
  );
```

**JSON and Boolean Column Usage:**
```typescript
export const passKeyCredentialTable = sqliteTable("passkey_credentials", {
  id: text("id").primaryKey().$defaultFn(createId).notNull(),
  userId: text("user_id").notNull().references(() => userTable.id),
  credentialId: text("credential_id").notNull().unique(),
  transports: text("transports", { mode: "json" }), // Stores string array
  counter: integer("counter").notNull().default(0),
  createdAt: integer("created_at", { mode: "timestamp" }).default(sql`CURRENT_TIMESTAMP`),
});
```