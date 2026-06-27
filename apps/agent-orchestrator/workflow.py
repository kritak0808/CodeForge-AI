import logging
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from graph_builder import compile_sdlc_graph
from checkpoint_manager import CheckpointManager

logger = logging.getLogger("agent-orchestrator.workflow-legacy")

# Maintain backward compatibility types
WorkflowStateDict = Dict[str, Any]

class PostgresCheckpointer:
    def __init__(self, db_url: str):
        self.mgr = CheckpointManager(db_url, "redis://localhost:6379/0")

    def save_checkpoint(self, workflow_id: str, state_name: str, state_data: Dict[str, Any]):
        self.mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node=state_name,
            execution_context=state_data.get("workflow_context", state_data),
            agent_outputs=state_data.get("agent_outputs", {}),
            errors=state_data.get("errors", [])
        )

    def load_checkpoint(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        return self.mgr.restore_checkpoint(workflow_id)

def build_workflow_graph() -> Any:
    """
    Legacy wrapper for test compatibility. Compiles and returns the LangGraph workflow graph.
    """
    logger.info("Resolving build_workflow_graph to compile_sdlc_graph for system execution.")
    return compile_sdlc_graph()
