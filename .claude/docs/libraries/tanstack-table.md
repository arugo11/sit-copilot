# TanStack Table + TanStack Virtual

## Overview
- **TanStack Table (React Table)**: Headless UI library for building powerful tables
- **TanStack Virtual**: Virtualization library for efficiently rendering large lists/tables

## Version Info (2025)
- **TanStack Table**: v8.20.x
- **TanStack Virtual**: v3.10.x
- **Key change**: v8 is a complete rewrite from v7 with hooks-based API

## Installation
```bash
npm install @tanstack/react-table

# For virtualization
npm install @tanstack/react-virtual
```

## Basic TanStack Table Setup

### Column Definition
```tsx
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'

type Person = {
  firstName: string
  lastName: string
  age: number
  visits: number
  status: string
  progress: number
}

const columnHelper = createColumnHelper<Person>()

const columns = [
  columnHelper.accessor('firstName', {
    header: 'First Name',
    cell: info => info.getValue(),
  }),
  columnHelper.accessor('lastName', {
    header: 'Last Name',
    cell: info => info.getValue(),
  }),
  columnHelper.accessor('age', {
    header: 'Age',
    cell: info => info.getValue(),
  }),
  columnHelper.accessor('visits', {
    header: 'Visits',
    cell: info => info.getValue(),
  }),
  columnHelper.accessor('status', {
    header: 'Status',
    cell: info => info.getValue(),
  }),
  columnHelper.accessor('progress', {
    header: 'Profile Progress',
    cell: info => info.getValue(),
  }),
]
```

### Table Component
```tsx
function DataTable({ data }: { data: Person[] }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })
  
  return (
    <table className="border-collapse w-full">
      <thead>
        {table.getHeaderGroups().map(headerGroup => (
          <tr key={headerGroup.id}>
            {headerGroup.headers.map(header => (
              <th key={header.id} className="border p-2">
                {header.isPlaceholder
                  ? null
                  : flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map(row => (
          <tr key={row.id}>
            {row.getVisibleCells().map(cell => (
              <td key={cell.id} className="border p-2">
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

## Advanced Features

### 1. Sorting
```tsx
const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(), // Enable sorting
  state: {
    sorting: [{ id: 'age', desc: true }],
  },
  onSortingChange: setSorting,
})

// Column with sorting
columnHelper.accessor('age', {
  header: () => <span>Age</span>,
  cell: info => info.getValue(),
})
```

### 2. Filtering
```tsx
const [globalFilter, setGlobalFilter] = useState('')

const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  getFilteredRowModel: getFilteredRowModel(), // Enable filtering
  state: {
    globalFilter,
  },
  onGlobalFilterChange: setGlobalFilter,
})

// Column filter
columnHelper.accessor('firstName', {
  header: 'First Name',
  cell: info => info.getValue(),
  meta: {
    filterVariant: 'text',
  },
})
```

### 3. Pagination
```tsx
const [pagination, setPagination] = useState({
  pageIndex: 0,
  pageSize: 10,
})

const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  getPaginationRowModel: getPaginationRowModel(), // Enable pagination
  state: { pagination },
  onPaginationChange: setPagination,
})

// Pagination controls
<div className="flex items-center gap-2">
  <button onClick={() => table.setPageIndex(0)} disabled={!table.getCanPreviousPage()}>
    {'<<'}
  </button>
  <button onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
    {'<'}
  </button>
  <button onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
    {'>'}
  </button>
  <button onClick={() => table.setPageIndex(table.getPageCount() - 1)} disabled={!table.getCanNextPage()}>
    {'>>'}
  </button>
  <span className="flex items-center gap-1">
    <div>Page</div>
    <strong>
      {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
    </strong>
  </span>
</div>
```

### 4. Row Selection
```tsx
const [rowSelection, setRowSelection] = useState({})

const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  state: {
    rowSelection,
  },
  onRowSelectionChange: setRowSelection,
  enableRowSelection: true, // Enable row selection
})

// Checkbox column
const columns = [
  {
    id: 'select',
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllRowsSelected()}
        onChange={table.getToggleAllRowsSelectedHandler()}
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
      />
    ),
  },
  // ... other columns
]
```

## Virtualization with TanStack Virtual

### Basic Virtual List
```tsx
import { useVirtualizer } from '@tanstack/react-virtual'

function VirtualList({ items }: { items: string[] }) {
  const parentRef = useRef<HTMLDivElement>(null)
  
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50, // Estimated row height
    overscan: 5, // Render extra rows for smoother scrolling
  })
  
  return (
    <div ref={parentRef} className="h-96 overflow-auto">
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map(virtualItem => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            {items[virtualItem.index]}
          </div>
        ))}
      </div>
    </div>
  )
}
```

### Virtual Table
```tsx
function VirtualTable({ data }: { data: Person[] }) {
  const tableContainerRef = useRef<HTMLDivElement>(null)
  
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })
  
  const { rows } = table.getRowModel()
  
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => 50, // Row height
    overscan: 5,
  })
  
  const virtualRows = virtualizer.getVirtualItems()
  
  return (
    <div ref={tableContainerRef} className="h-96 overflow-auto">
      <table className="w-full">
        <thead>
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th key={header.id} className="border p-2">
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {virtualRows.map(virtualRow => {
            const row = rows[virtualRow.index]
            return (
              <tr key={row.id} style={{ height: `${virtualRow.size}px` }}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="border p-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
```

## Dynamic Row Height
```tsx
const virtualizer = useVirtualizer({
  count: rows.length,
  getScrollElement: () => tableContainerRef.current,
  estimateSize: () => 50, // Initial estimate
  measureElement: element => {
    // Measure actual height after render
    return element?.getBoundingClientRect().height ?? 50
  },
})
```

## Column Resizing
```tsx
const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  enableColumnResizing: true,
  columnResizeMode: 'onChange', // or 'onEnd'
  state: {
    columnResizing,
  },
  onColumnResizingChange: setColumnResizing,
})

// Resizable header
<th
  {...{ style: { width: column.getSize() } }}
>
  {flexRender(header.column.columnDef.header, header.getContext())}
  <div
    onMouseDown={header.getResizeHandler()}
    onTouchStart={header.getResizeHandler()}
    className="absolute right-0 top-0 h-full w-1 cursor-col-resize bg-blue-500"
  />
</th>
```

## Common Pitfalls

### 1. Missing Key Props
Always use the row's `id` as the key:
```tsx
// ❌
{rows.map((row, index) => <tr key={index}>...</tr>)}

// ✅
{rows.map(row => <tr key={row.id}>...</tr>)}
```

### 2. Re-creating Columns on Every Render
```tsx
// ❌ Creates new columns on every render
const columns = [
  columnHelper.accessor('name', { header: 'Name' })
]

// ✅ Memoize columns
const columns = useMemo(() => [
  columnHelper.accessor('name', { header: 'Name' })
], [])
```

### 3. Virtual Row Measurement Issues
For dynamic heights, ensure `measureElement` is configured correctly and rows have stable references.

## Best Practices

1. **Memoize columns**: Prevent unnecessary re-renders
2. **Use row IDs**: Ensure each row has a unique ID
3. **Estimate sizes accurately**: Better estimates = smoother scrolling
4. **Overscan appropriately**: Balance performance and smoothness
5. **Use column helpers**: Type-safe column definitions

## Official Resources
- [TanStack Table Documentation](https://tanstack.com/table/latest)
- [TanStack Virtual Documentation](https://tanstack.com/virtual/latest)
- [GitHub Repository](https://github.com/TanStack/table)
