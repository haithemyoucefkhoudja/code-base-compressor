# Skill: TanStack React Table Data Grid System

## Summary
A headless data grid implementation using TanStack React Table v8 integrated with shadcn/ui Table primitives. The system provides a reusable `DataTable` component that supports manual server-side pagination, row-level navigation, and customizable column definitions via the `ColumnDef` API. It renders tabular data with header groups, cell flex rendering, and empty states while delegating pagination logic to parent components through callback props.

## Key Components
- **`DataTable`** (`src/components/data-table.tsx`): Main generic component wrapping `useReactTable`
- **`useReactTable`**: Core hook from `@tanstack/react-table` for table instance management
- **`flexRender`**: Utility from `@tanstack/react-table` for rendering cell and header content
- **`getCoreRowModel`**: Row model function for basic row processing
- **`ColumnDef<TData, TValue>`**: Type definition for column configuration arrays
- **Table UI Primitives** (`src/components/ui/table.tsx`):
  - `Table`: Root table container with overflow handling
  - `TableHeader`: Header section wrapper
  - `TableBody`: Body section wrapper
  - `TableRow`: Row component with hover and selected states
  - `TableHead`: Header cell component
  - `TableCell`: Data cell component
- **`UsersTable`**: Example implementation component (`src/app/admin/admin/components/users/users-table.tsx`)

## Behaviors & Rules
- **Manual Pagination Mode**: The table operates with `manualPagination: true`, requiring parent components to provide `pageCount`, `pageIndex`, and `pageSize` via props rather than calculating pagination internally.
- **Generic Type Safety**: The component uses TypeScript generics `<TData, TValue>` where `TData` represents the row data type and `TValue` represents cell values.
- **Row Navigation**: When `getRowHref` prop is provided, rows receive `cursor-pointer` class and clicking a row navigates using `row.original` as the argument to `getRowHref`.
- **Header Group Rendering**: Headers are rendered by mapping `table.getHeaderGroups()` and checking `header.isPlaceholder` to skip placeholder headers.
- **Cell Rendering**: Cells use `flexRender(cell.column.columnDef.cell, cell.getContext())` to support custom cell components.
- **Empty State**: When `table.getRowModel().rows` has no length, a single row spanning all columns displays "No results." with `h-24` height and centered text.
- **Row Model Access**: Data rows are accessed via `table.getRowModel().rows` rather than the raw `data` prop to ensure processed row objects with metadata (like `id`, `getIsSelected()`, `getVisibleCells()`).
- **Pagination Display**: Shows range text in format "Showing {start} to {end} of {total} {itemName}" using `pageIndex * pageSize + 1` for start index and `Math.min((pageIndex + 1) * pageSize, totalCount)` for end index.
- **Page Size Options**: Default options are `[10, 20, 30, 40, 50]` but configurable via `pageSizeOptions` prop.
- **Column Exclusion**: The `excludeClickableColumns` prop (string array) identifies columns where row click navigation should be disabled (though the click handler logic is implemented in the consuming component).

## Inputs & Outputs

### Props Interface (`DataTableProps<TData, TValue>`)
**Inputs:**
- `columns: ColumnDef<TData, TValue>[]` - Column definition array configuring headers, accessors, and cell renderers
- `data: TData[]` - Array of row data objects
- `pageCount: number` - Total number of pages (calculated server-side)
- `pageIndex: number` - Current page index (0-based)
- `pageSize: number` - Number of items per page
- `onPageChange: (page: number) => void` - Callback when user changes page
- `onPageSizeChange: (size: number) => void` - Callback when user changes page size
- `totalCount: number` - Total number of items across all pages
- `itemNameSingular: string` - Singular noun for item type (e.g., "user")
- `itemNamePlural: string` - Plural noun for item type (e.g., "users")
- `pageSizeOptions?: number[]` - Optional array of page size choices (defaults to `[10, 20, 30, 40, 50]`)
- `getRowHref?: (row: TData) => string` - Optional function returning navigation path for row clicks
- `excludeClickableColumns?: string[]` - Optional array of column IDs to exclude from row click behavior

**Internal State:**
- `table` instance returned by `useReactTable` hook containing row models, header groups, and pagination state

**Outputs (Render):**
- JSX structure containing `Table`, `TableHeader`, `TableBody` with mapped rows and cells
- Pagination controls displaying item count range and total
- "No results" fallback when data array is empty

## Dependencies
- **`@tanstack/react-table`**: Core headless table library providing `useReactTable`, `flexRender`, `getCoreRowModel`, and `ColumnDef` types
- **`@/components/ui/table`**: Local shadcn/ui table primitives (`Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`)
- **`@/lib/utils`**: Utility module exporting `cn()` for Tailwind class merging
- **`react`**: React library for `useState` (in example implementations) and JSX rendering

## Code Patterns

### Table Instance Configuration
```typescript
const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  pageCount,
  state: {
    pagination: {
      pageIndex,
      pageSize,
    },
  },
  manualPagination: true,
})
```

### Header Rendering Pattern
```typescript
<TableHeader>
  {table.getHeaderGroups().map((headerGroup) => (
    <TableRow key={headerGroup.id}>
      {headerGroup.headers.map((header) => (
        <TableHead key={header.id}>
          {header.isPlaceholder
            ? null
            : flexRender(
                header.column.columnDef.header,
                header.getContext()
              )}
        </TableHead>
      ))}
    </TableRow>
  ))}
</TableHeader>
```

### Row and Cell Rendering with Navigation
```typescript
<TableBody>
  {table.getRowModel().rows?.length ? (
    table.getRowModel().rows.map((row) => (
      <TableRow
        key={row.id}
        data-state={row.getIsSelected() && "selected"}
        className={cn(
          getRowHref && "cursor-pointer hover:bg-muted/50"
        )}
        onClick={() => {
          if (getRowHref) {
            const href = getRowHref(row.original)
            // Navigation logic here
          }
        }}
      >
        {row.getVisibleCells().map((cell) => (
          <TableCell key={cell.id}>
            {flexRender(
              cell.column.columnDef.cell,
              cell.getContext()
            )}
          </TableCell>
        ))}
      </TableRow>
    ))
  ) : (
    <TableRow>
      <TableCell
        colSpan={columns.length}
        className="h-24 text-center"
      >
        No results.
      </TableCell>
    </TableRow>
  )}
</TableBody>
```

### Pagination Range Display
```typescript
<div className="text-sm text-muted-foreground">
  Showing {pageIndex * pageSize + 1} to {Math.min((pageIndex + 1) * pageSize, totalCount)} of {totalCount} {totalCount === 1 ? itemNameSingular : itemNamePlural}
</div>
```

### Column Definition Example
```typescript
const columns: ColumnDef<User>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <div className="font-medium">{row.getValue("name")}</div>,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status") as string
      return <Badge variant={status === "active" ? "default" : "secondary"}>{status}</Badge>
    },
  },
]
```