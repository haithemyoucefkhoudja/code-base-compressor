# Skill: React Flow / XYFlow (Visual Node-Based Workflow Editor)

## Summary
This skill implements a visual node-based workflow editor using the React Flow (XYFlow) library. It provides a canvas for creating, connecting, and configuring workflow nodes with features including an inspector panel for node configuration, context menus for quick actions, undo/redo history management, and persistence via server actions. The implementation uses a split state pattern tracking both frontend (`feNodes`) and backend (`beNodes`) node representations, with Zod schemas for type-safe graph serialization and ZSA server actions for workflow persistence.

## Key Components

**Core Editor Components:**
- `FlowEditor` (DEF in `src\components\canvas\flow-editor.tsx`) - Main container component
- `FlowEditorContent` (DEF in `src\components\canvas\flow-editor.tsx`) - Editor implementation with React Flow hooks
- `WorkflowEditorWrapper` (DEF in `src\app\dashboard\dashboard\projects\projectId\workflow\workflowId\editor-wrapper.tsx`) - Wrapper providing ReactFlowProvider
- `WorkflowPage` (DEF in `src\app\dashboard\dashboard\projects\projectId\workflow\workflowId\page.tsx`) - Page component fetching workflow data

**UI Panels & Dialogs:**
- `InspectorPanel` (DEF in `src\components\canvas\inspector-panel.tsx`) - Side panel for editing selected node properties
- `NodeContextMenu` (DEF in `src\components\canvas\node-context-menu.tsx`) - Right-click context menu for nodes
- `NodeRulesDialog` (DEF in `src\components\canvas\node-rules-dialog.tsx`) - Dialog for managing node validation rules
- `AddNodeDialog` (DEF in `src\components\canvas\add-node-dialog.tsx`) - Dialog for adding new nodes with category selection

**State & Hooks:**
- `useReactFlow` (CALL from `"@xyflow/react"`) - Hook accessing React Flow instance methods (getNodes, setNodes, project, fitView)
- `useTransactionStore` (CALL from `"@/state/transaction"`) - Zustand store providing undo/redo history via snapshots

**Schemas (Zod):**
- `WorkflowGraphSchema` (CONST) - Schema for entire graph state (nodes, edges, viewport)
- `ArroNodeSchema` (CONST) - Schema for node definitions (id, type, position, data with label/tool/category)
- `ArroEdgeSchema` (CONST) - Schema for edge definitions (source, target, type)
- `NodeRuleSchema` (CONST) - Schema for node validation rules (propertyKey, condition, message)
- `NodeCategorySchema` (CONST) - Enum schema for node categories (trigger, action, condition, transform, output)

**Server Actions (ZSA):**
- `saveWorkflowAction` (CONST) - Persists workflow graph to database
- `getWorkflowAction` (CONST) - Retrieves workflow by projectId and workflowId
- `createWorkflowAction` (CONST) - Creates new workflow with initial empty graph

## Behaviors & Rules

**Node State Management:**
- Nodes are tracked in dual state: `feNodes` (frontend/display state) and `beNodes` (backend/persisted state)
- Node updates trigger `onNodeUpdate` callback which calls `setNodes` and `takeSnapshot` for history
- New nodes are created via `newNode` constant with generated IDs and category metadata

**Selection & Inspection:**
- Clicking a node sets `selectedNode` state and displays `InspectorPanel`
- `setSelectedNodeId` is called to track current selection
- Inspector panel accesses `selectedNode.data.label`, `selectedNode.rules`, and `selectedNode.properties`
- Pane click clears selection via `onPaneClick` pattern

**History & Undo/Redo:**
- Every significant state change calls `takeSnapshot({ nodes, edges })` before mutation
- `redo` action available for restoring future states
- History tracked in `useTransactionStore` with past/present/future array pattern

**Node Rules:**
- Rules managed via `NodeRulesDialog` opened from `InspectorPanel` or `NodeContextMenu`
- Rules array accessed via `data.rules.length` and `selectedNode.rules`
- Rule structure includes `id`, `propertyKey`, `condition`, and `message` fields

**Persistence:**
- Save operation serializes current `nodes` and `edges` to `WorkflowGraphSchema`
- `saveWorkflowAction` receives graph JSON and updates database via `db.update.set.where` pattern
- Initial load hydrates editor via `initialGraph.nodes` and `initialGraph.edges`

**Node Creation:**
- `AddNodeDialog` opened via `setIsAddNodeDialogOpen(true)`
- Node type inferred via `inferNodeDetails` utility from `@/lib/arroflow/generator`
- Categories include: "trigger", "action", "condition", "transform", "output"
- New node positioned using `screenToFlowPosition` from `useReactFlow`

**Context Menu Operations:**
- Right-click on node opens `NodeContextMenu` with options:
  - Duplicate: calls `data.onDuplicate` with node data
  - Add Rule: calls `data.onAddRule` opening rules dialog
  - Delete: removes node and connected edges

**Graph Validation:**
- `WorkflowGraphSchema` validates structure before save
- `ArroNodeSchema` enforces required fields: `id`, `type`, `position` (x/y), `data.label`, `data.category`
- `NodeCategorySchema` restricts to predefined category strings

## Inputs & Outputs

**Component Props:**
- `initialGraph?: WorkflowGraphSchema` - Optional initial state with `nodes` and `edges` arrays
- `onSave?: (graph: WorkflowGraphSchema) => void` - Optional callback for save events
- `onGenerate?: (graph: WorkflowGraphSchema) => void` - Optional callback for code generation
- `workflow: { id, name, graph, projectId }` - Workflow data passed to `WorkflowEditorWrapper`

**State Outputs:**
- `nodes` / `setNodes` - Current node array and setter
- `edges` / `setEdges` - Current edge array and setter  
- `selectedNode` - Currently selected node object or null
- `isAddNodeDialogOpen` - Boolean controlling add node dialog visibility

**Server Action I/O:**
- `getWorkflowAction` input: `{ projectId: string, workflowId: string }`
- `saveWorkflowAction` input: `{ workflowId: string, graph: WorkflowGraphSchema }`
- `createWorkflowAction` input: `{ name: string, teamId: string }`, output: `{ workflowId: string }`

**Schema Types:**
- `NodeProps` (from `"@xyflow/react"`) - Type for custom node component props
- `WorkflowGraph` - Inferred type from `WorkflowGraphSchema` containing nodes, edges, rules, viewport

## Dependencies

**Core Library:**
- `"@xyflow/react"` - React Flow library providing `ReactFlow`, `useReactFlow`, `NodeProps`, `Handle`, `Background`, `Controls`, `MiniMap`, `ReactFlowProvider`

**State Management:**
- `"zustand"` (implied via `useTransactionStore` pattern) - For transaction history store
- `"@/state/transaction"` - Local transaction store implementation

**Validation & Types:**
- `"zod"` - Schema validation for `WorkflowGraphSchema`, `ArroNodeSchema`, `ArroEdgeSchema`, `NodeRuleSchema`, `NodeCategorySchema`

**Server Actions:**
- `"zsa"` - Server action framework for `saveWorkflowAction`, `getWorkflowAction`, `createWorkflowAction`
- `"zsa-react"` - Client-side hooks for executing server actions

**Utilities:**
- `"@/lib/arroflow/generator"` - Provides `inferNodeDetails` for node type inference
- `"@/lib/arroflow/schemas"` - Schema definitions
- `"@/lib/arroflow/transaction-store"` - History management (alternative path to `@/state/transaction`)

## Code Patterns

**React Flow Setup with Provider:**
```typescript
// WorkflowEditorWrapper pattern
import { ReactFlowProvider } from "@xyflow/react";
import { FlowEditor } from "@/components/canvas/flow-editor";

export function WorkflowEditorWrapper({ workflow }) {
  return (
    <ReactFlowProvider>
      <FlowEditor
        initialGraph={workflow.graph}
        onSave={handleSave}
        onGenerate={handleGenerate}
      />
    </ReactFlowProvider>
  );
}
```

**Editor Content with Hooks:**
```typescript
// FlowEditorContent pattern
import { useReactFlow, useNodesState, useEdgesState } from "@xyflow/react";
import { useTransactionStore } from "@/state/transaction";

export function FlowEditorContent({ initialGraph, onSave }) {
  const { screenToFlowPosition, fitView } = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialGraph?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialGraph?.edges || []);
  const { takeSnapshot, redo } = useTransactionStore();
  const [selectedNode, setSelectedNode] = useState(null);
  
  // Node update with history snapshot
  const onNodeUpdate = useCallback((updatedNode) => {
    setNodes((nds) => nds.map((n) => (n.id === updatedNode.id ? updatedNode : n)));
    takeSnapshot({ nodes, edges });
  }, [nodes, edges, setNodes, takeSnapshot]);
}
```

**Node Drop Handler:**
```typescript
const onDrop = useCallback((event) => {
  event.preventDefault();
  const type = event.dataTransfer.getData("application/reactflow");
  const category = event.dataTransfer.getData("nodeCategory");
  
  const position = screenToFlowPosition({
    x: event.clientX,
    y: event.clientY,
  });

  const newNode = {
    id: `${type}-${Date.now()}`,
    type,
    position,
    data: { label: `${type} node`, category },
  };

  setNodes((nds) => nds.concat(newNode));
  takeSnapshot({ nodes: nodes.concat(newNode), edges });
}, [screenToFlowPosition, setNodes, takeSnapshot, nodes, edges]);
```

**Schema Definitions:**
```typescript
import { z } from "zod";

export const NodeCategorySchema = z.enum([
  "trigger", "action", "condition", "transform", "output"
]);

export const ArroNodeSchema = z.object({
  id: z.string(),
  type: z.string(),
  position: z.object({ x: z.number(), y: z.number() }),
  data: z.object({
    label: z.string(),
    tool: z.string(),
    category: NodeCategorySchema,
    rules: z.array(NodeRuleSchema).optional()
  })
});

export const WorkflowGraphSchema = z.object({
  nodes: z.array(ArroNodeSchema),
  edges: z.array(ArroEdgeSchema),
  viewport: z.object({ x: z.number(), y: z.number(), zoom: z.number() }).optional()
});
```

**Server Action Pattern:**
```typescript
import { createServerAction } from "zsa";
import { z } from "zod";

export const saveWorkflowAction = createServerAction()
  .input(z.object({
    workflowId: z.string(),
    graph: WorkflowGraphSchema
  }))
  .handler(async ({ input }) => {
    const { workflowId, graph } = input;
    await db.update(workflowTable)
      .set({ graphJson: JSON.stringify(graph), updatedAt: new Date() })
      .where(eq(workflowTable.id, workflowId));
    return { success: true };
  });
```

**Inspector Panel Integration:**
```typescript
// In FlowEditorContent return
<div className="flex h-full w-full">
  <div className="flex-1 relative">
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onNodeClick={(_, node) => setSelectedNode(node)}
      onPaneClick={() => setSelectedNode(null)}
    >
      <Background />
      <Controls />
    </ReactFlow>
  </div>
  
  {selectedNode && (
    <InspectorPanel
      selectedNode={selectedNode}
      onNodeUpdate={onNodeUpdate}
    />
  )}
</div>
```

**Context Menu Implementation:**
```typescript
import { ContextMenu, ContextMenuContent, ContextMenuItem } from "@/components/ui/context-menu";

export function NodeContextMenu({ node, onDuplicate, onDelete, onAddRule }) {
  return (
    <ContextMenu>
      <ContextMenuTrigger>{/* Node content */}</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem onClick={() => onDuplicate(node)}>Duplicate</ContextMenuItem>
        <ContextMenuItem onClick={() => onAddRule(node)}>Add Rule</ContextMenuItem>
        <ContextMenuItem onClick={() => onDelete(node.id)} className="text-destructive">
          Delete
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
```

**Transaction Store Pattern:**
```typescript
import { create } from 'zustand';

export const useTransactionStore = create((set, get) => ({
  past: [],
  present: { nodes: [], edges: [] },
  future: [],
  
  takeSnapshot: ({ nodes, edges }) => {
    const { present, past } = get();
    set({
      past: [...past, present],
      present: { nodes, edges },
      future: [] // Clear redo stack on new action
    });
  },
  
  redo: () => {
    const { past, present, future } = get();
    if (future.length === 0) return;
    const next = future[0];
    set({
      past: [...past, present],
      present: next,
      future: future.slice(1)
    });
  }
}));
```