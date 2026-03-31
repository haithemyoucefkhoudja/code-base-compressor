# Skill: React Flow / XYFlow (Visual Node-Based Workflow Editor)

## Summary
This skill implements a visual node-based workflow editor using React Flow (XYFlow) library. It provides a canvas for creating, connecting, and configuring workflow nodes, with side-panel property inspection, context menus for node operations, and Zod-schematized persistence to a database via server actions. The architecture separates concerns between canvas rendering (`FlowEditor`), node configuration (`InspectorPanel`), interaction menus (`NodeContextMenu`), and rule management (`NodeRulesDialog`), all backed by a Zustand store and Zod validation schemas (`ArroNodeSchema`, `NodeRuleSchema`).

## Key Components

| Component | Role |
|-----------|------|
| `FlowEditor` | Main container component that wraps the canvas with `ReactFlowProvider` to establish React Flow context. |
| `FlowEditorContent` | Inner canvas component containing `ReactFlow`, `Background`, `Controls`, and `MiniMap`. Manages `nodes` and `edges` state via `useNodesState` and `useEdgesState`. |
| `InspectorPanel` | Side panel for editing the currently selected node's properties. Uses `react-hook-form` with `FormField`, `FormControl`, and `FormLabel` for data binding. |
| `NodeContextMenu` | Right-click context menu for nodes using `@radix-ui/react-context-menu` primitives (`ContextMenuTrigger`, `ContextMenuContent`, `ContextMenuItem`, `ContextMenuSub`). Supports duplicate, delete, and add rule actions. |
| `NodeRulesDialog` | Dialog component for managing node connection rules and constraints. |
| `AddNodeDialog` | Dialog for creating new nodes with category filtering and selection. |
| `CustomNode` | Custom node type component using `Handle` from `@xyflow/react` to define connection points. |
| `ArroNodeSchema` | Zod schema defining the structure of workflow nodes (id, category, tool, label, position, config, properties, rules, validationStatus). |
| `ArroEdgeSchema` | Zod schema defining edge structure (id, source, target). |
| `NodeRuleSchema` | Zod schema for node connection rules, supporting property-based, category-based, conditional, and platform-specific rule types. |
| `NodeCategorySchema` | Zod schema for node category classification. |
| `saveWorkflowAction` | Server action (ZSA) that serializes the workflow graph to JSON and persists to `workflowTable`. |
| `getWorkflowAction` | Server action that retrieves a workflow by ID and deserializes the graph. |
| `useWorkflowStore` | Zustand store managing workflow state including `nodes`, `edges`, `selectedNode`, and history tracking. |

## Behaviors & Rules

- **Node Structure**: Every node must conform to `ArroNodeSchema`, requiring `id` (string), `category` (NodeCategorySchema), `tool` (string), `label` (string), `position` (x/y coordinates), `config` (record), `properties` (record), and `rules` (array).
- **Validation Status**: Nodes track validation state via `validationStatus` object containing `hasErrors` (boolean), `hasWarnings` (boolean), `errorCount` (number), and `warningCount` (number).
- **Connection Rules**: Nodes enforce connection constraints through `rules` array (validated by `NodeRuleSchema`), which may include:
  - `propertyKey` constraints
  - `allowedTargetCategories` arrays
  - Conditional `if/require` logic blocks
  - Platform and runtime restrictions
- **Graph Serialization**: The workflow graph is serialized to `graphJson` (string) for database storage, converting between frontend node representations (`feNodes`), backend representations (`beNodes`), and database storage format (`dbNodes`).
- **Selection State**: When a node is selected, `selectedNode` is set in the store, triggering `InspectorPanel` to render with `selectedNode.rules`, `selectedNode.properties`, and `selectedNode.data.label` accessible for editing.
- **Connection Handling**: Edges are created using `addEdge` from `@xyflow/react` within the `onConnect` callback, which updates the `edges` state via `setEdges`.
- **Context Menu Actions**: Right-clicking a node opens `NodeContextMenu` with options to duplicate (copy node with new ID), delete (remove from `setNodes`), or add rules (open `NodeRulesDialog`).
- **Form Integration**: `InspectorPanel` uses `react-hook-form` with `zodResolver` for real-time validation of node properties, accessing form controls via `form.control` and updating values via `form.setValue`.
- **History Tracking**: State changes trigger `takeSnapshot` for undo/redo functionality, storing previous states in `history` array with `newHistory.length` checks.
- **Server Action Integration**: `saveWorkflowAction` accepts `workflowId` and `graphJson`, executing `db.update` with `eq` constraints. `getWorkflowAction` queries using `db.query.workflowTable.findFirst` with relations.

## Inputs & Outputs

**FlowEditor Props:**
- `initialGraph?: { nodes: CustomNode[], edges: CustomEdge[] }` - Initial workflow state
- `onSave?: (graph: any) => void` - Callback when save is triggered
- `onGenerate?: () => void` - Callback for generation actions

**FlowEditorContent Props:**
- Same as `FlowEditor` - passed through from parent

**InspectorPanel Props:**
- `selectedNode: CustomNode | null` - Currently selected node for editing
- `onNodeUpdate: (nodeId: string, data: any) => void` - Callback when node data changes

**NodeContextMenu Props:**
- `children: React.ReactNode` - Trigger element (the node)
- `nodeId: string` - ID of the node to operate on
- `onDuplicate: (node: any) => void` - Duplicate handler
- `onDelete: (nodeId: string) => void` - Delete handler  
- `onAddRule: (node: any) => void` - Add rule handler

**Server Action Inputs:**
- `saveWorkflowAction`: `{ workflowId: string, graphJson: string }`
- `getWorkflowAction`: `string` (workflowId)
- `createWorkflowAction`: `{ name: string, projectId: string }`

**Schema Types:**
- `ArroNodeSchema` output: Object with `id`, `category`, `tool`, `label`, `position`, `config`, `properties`, `rules`, `validationStatus`, `data`
- `NodeRuleSchema` output: Union of rule types with `id`, `type`, `severity`, `enabled`, and conditional fields

## Dependencies

- `@xyflow/react` - Core library providing `ReactFlow`, `NodeProps`, `Edge`, `Node`, `useReactFlow`, `Handle`, `Position`, `ReactFlowProvider`, `Background`, `Controls`, `MiniMap`, `useNodesState`, `useEdgesState`, `addEdge`, `Connection`
- `zod` - Schema validation for `ArroNodeSchema`, `ArroEdgeSchema`, `NodeRuleSchema`
- `zsa` / `zsa-react` - Server action creation and client-side execution hooks (`useServerAction`)
- `react-hook-form` - Form state management in `InspectorPanel` (`useForm`, `FormField`, `FormControl`)
- `@hookform/resolvers/zod` - Zod resolver for react-hook-form (`zodResolver`)
- `@radix-ui/react-context-menu` - Context menu primitives (`ContextMenu`, `ContextMenuTrigger`, `ContextMenuContent`, `ContextMenuItem`, `ContextMenuSub`, `ContextMenuSubTrigger`, `ContextMenuSubContent`, `ContextMenuCheckboxItem`, `ContextMenuRadioItem`, `ContextMenuRadioGroup`, `ContextMenuLabel`, `ContextMenuGroup`, `ContextMenuPortal`, `ContextMenuSeparator`)
- `zustand` - State management for workflow store (`create`, `useWorkflowStore`)
- `motion/react` - Animation components for custom nodes (`motion.div`)
- `drizzle-orm` - Database operations in server actions (`eq`, `and`, `db.update`, `db.query`)

## Code Patterns

**Canvas Setup with Provider:**
```typescript
// src/components/canvas/flow-editor.tsx
import { ReactFlowProvider } from '@xyflow/react'
import { FlowEditorContent } from './flow-editor-content'

export function FlowEditor(props: FlowEditorProps) {
  return (
    <ReactFlowProvider>
      <FlowEditorContent {...props} />
    </ReactFlowProvider>
  )
}
```

**Canvas Content with State Management:**
```typescript
// src/components/canvas/flow-editor-content.tsx
'use client'

import { useCallback } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
  Connection
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

export function FlowEditorContent({ 
  initialGraph, 
  onSave, 
  onGenerate 
}: FlowEditorContentProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialGraph?.nodes || [])
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialGraph?.edges || [])
  const reactFlowInstance = useReactFlow()

  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge(connection, eds))
  }, [setEdges])

  // Additional logic for node management via reactFlowInstance
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
    >
      <Background />
      <Controls />
      <MiniMap />
    </ReactFlow>
  )
}
```

**Node Schema Definition:**
```typescript
// src/schemas/workflow.ts
import { z } from "zod"

export const NodeCategorySchema = z.string()

export const NodeRuleSchema = z.object({
  id: z.string(),
  type: z.literal(/* specific type */),
  severity: z.union([/* severity options */]),
  enabled: z.boolean(),
  propertyKey: z.string().optional(),
  allowedTargetCategories: z.array(z.string()).optional(),
  if: z.object({
    propertyKey: z.string(),
    equals: z.string()
  }).optional(),
  require: z.object({
    propertyKey: z.string()
  }).optional(),
  platform: z.union([/* platform options */]).optional(),
  disallowRuntime: z.array(z.string()).optional()
})

export const ArroNodeSchema = z.object({
  id: z.string(),
  category: NodeCategorySchema,
  tool: z.string(),
  label: z.string(),
  position: z.object({
    x: z.number(),
    y: z.number()
  }),
  config: z.record(z.any()).default({}),
  properties: z.record(z.string()).default({}),
  rules: z.array(NodeRuleSchema).default([]),
  validationStatus: z.object({
    hasErrors: z.boolean(),
    hasWarnings: z.boolean(),
    errorCount: z.number(),
    warningCount: z.number()
  }).optional(),
  data: z.object({
    label: z.string(),
    category: z.string(),
    tool: z.string(),
    slug: z.string(),
    logoUrl: z.string().nullable().optional()
  }).passthrough().optional()
})
```

**Custom Node with Handles:**
```typescript
// src/components/canvas/CustomNode.tsx
import { Handle, Position, NodeProps } from "@xyflow/react"
import { motion } from "motion/react"

export const CustomNode: React.FC<NodeProps> = ({ data, selected }) => {
  return (
    <motion.div 
      className={`node-container ${selected ? 'selected' : ''}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <Handle
        type="source"
        position={Position.Right}
        className="handle-source"
      />
      
      <div className="node-content">
        <span>{data.label}</span>
      </div>

      <Handle
        type="target"
        position={Position.Left}
        className="handle-target"
      />
    </motion.div>
  )
}
```

**Property Access Patterns:**
```typescript
// Node property extraction patterns observed
const extractNodeProps = (n: WorkflowNode) => {
  const nodeId = n.id
  const nodeCategory = n.category
  const nodeTool = n.tool
  const nodeLabel = n.data.label
  
  return { id: nodeId, category: nodeCategory, tool: nodeTool, label: nodeLabel }
}

const extractComponentProps = (component: WorkflowComponent) => {
  const { name, id, slug, category } = component
  return { name, id, slug, category }
}
```

**Server Action for Persistence:**
```typescript
// src/actions/workflow.ts
"use server"

import { createServerAction } from "zsa"
import { z } from "zod"
import { db } from "@/db"
import { workflowTable } from "@/db/schema"
import { eq } from "drizzle-orm"

export const saveWorkflowAction = createServerAction()
  .input(z.object({
    workflowId: z.string(),
    graphJson: z.string()
  }))
  .handler(async ({ input }) => {
    await db.update(workflowTable)
      .set({ 
        graphJson: input.graphJson, 
        updatedAt: new Date() 
      })
      .where(eq(workflowTable.id, input.workflowId))
    
    return { success: true }
  })

export const getWorkflowAction = createServerAction()
  .input(z.string())
  .handler(async ({ input: workflowId }) => {
    const workflow = await db.query.workflowTable.findFirst({
      where: eq(workflowTable.id, workflowId),
      with: { project: true }
    })
    
    if (!workflow) throw new Error("Workflow not found")
    return workflow
  })
```

**Context Menu Implementation:**
```typescript
// src/components/canvas/node-context-menu.tsx
import {
  ContextMenu,
  ContextMenuTrigger,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSub,
  ContextMenuSubTrigger,
  ContextMenuSubContent,
  ContextMenuCheckboxItem,
  ContextMenuRadioItem,
  ContextMenuRadioGroup,
  ContextMenuLabel,
  ContextMenuGroup,
  ContextMenuPortal,
  ContextMenuSeparator,
} from "@radix-ui/react-context-menu"

export function NodeContextMenu({ children, nodeId, onDuplicate, onDelete, onAddRule }: NodeContextMenuProps) {
  const { getNode } = useReactFlow()
  const selectedNode = getNode(nodeId)
  
  return (
    <ContextMenu>
      <ContextMenuTrigger>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuLabel>Node Actions</ContextMenuLabel>
        <ContextMenuSeparator />
        <ContextMenuGroup>
          <ContextMenuItem onSelect={() => onDuplicate(selectedNode)}>
            Duplicate
          </ContextMenuItem>
          <ContextMenuItem onSelect={() => onDelete(nodeId)}>
            Delete
          </ContextMenuItem>
        </ContextMenuGroup>
        {selectedNode?.data?.rules && (
          <ContextMenuSub>
            <ContextMenuSubTrigger>Rules</ContextMenuSubTrigger>
            <ContextMenuSubContent>
              {selectedNode.data.rules.map((rule) => (
                <ContextMenuCheckboxItem key={rule.id}>
                  {rule.condition}
                </ContextMenuCheckboxItem>
              ))}
            </ContextMenuSubContent>
          </ContextMenuSub>
        )}
        <ContextMenuPortal>
          <ContextMenuRadioGroup>
            <ContextMenuRadioItem value="option1">Option 1</ContextMenuRadioItem>
          </ContextMenuRadioGroup>
        </ContextMenuPortal>
      </ContextMenuContent>
    </ContextMenu>
  )
}
```