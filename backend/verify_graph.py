from app.graph.builder import build_graph
from app.graph.state import (
    STEP_APPROVAL, STEP_VALIDATE_TERRAFORM, STEP_CREATE_PR, STEP_GENERATE_TERRAFORM,
    STEP_TERRAFORM_PREVIEW, GlueJobState
)
from langgraph.checkpoint.memory import MemorySaver

# Build the graph
checkpointer = MemorySaver()
graph = build_graph(checkpointer)
print("✅ Graph built successfully\n")

# Get the graph structure
compiled_graph = graph
if hasattr(compiled_graph, '_graph'):
    g = compiled_graph._graph
    print(f"Internal graph attribute found")
    print(f"Nodes: {list(g.nodes.keys())[:3]}...") if g.nodes else print("No nodes")
else:
    print("✅ Graph compiled successfully")
    print(f"Graph type: {type(graph)}")
    
print("\nWorkflow chain (expected):")
print(f"{STEP_GENERATE_TERRAFORM} → {STEP_TERRAFORM_PREVIEW} → {STEP_APPROVAL} → {STEP_VALIDATE_TERRAFORM} → {STEP_CREATE_PR}")
