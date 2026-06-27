import logging
import time
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from opentelemetry import trace
from prometheus_client import Counter, Histogram
from state_models import WorkflowStateModel

logger = logging.getLogger("agent-orchestrator.graph-builder")
tracer = trace.get_tracer("agent-orchestrator.graph-builder")

# Prometheus Observability Metrics
NODE_EXECUTION_COUNT = Counter(
    "workflow_node_executions_total",
    "Total number of workflow node executions",
    ["node_name", "status"]
)
NODE_EXECUTION_LATENCY = Histogram(
    "workflow_node_execution_duration_seconds",
    "Workflow node execution latency in seconds",
    ["node_name"]
)

# Helper to trace node execution
def execute_node_with_telemetry(node_name: str, execute_fn) -> Any:
    def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Node [{node_name}] entered.")
        
        with tracer.start_as_current_span(f"workflow_node_{node_name.lower()}") as span:
            span.set_attribute("workflow_id", state.get("workflow_id", "unknown"))
            span.set_attribute("project_id", state.get("project_id", "unknown"))
            span.set_attribute("node_name", node_name)
            
            try:
                result = execute_fn(state)
                NODE_EXECUTION_COUNT.labels(node_name=node_name, status="success").inc()
                span.set_status(trace.StatusCode.OK)
                return result
            except Exception as e:
                logger.error(f"Error executing node [{node_name}]: {e}")
                NODE_EXECUTION_COUNT.labels(node_name=node_name, status="error").inc()
                span.record_exception(e)
                span.set_status(trace.StatusCode.ERROR, str(e))
                state["errors"] = state.get("errors", []) + [str(e)]
                state["current_state"] = "FAILED"
                raise
            finally:
                latency = time.time() - start_time
                NODE_EXECUTION_LATENCY.labels(node_name=node_name).observe(latency)
                logger.info(f"Node [{node_name}] exited in {latency:.4f}s.")
                
    return wrapper

# Raw Executor implementations
def _execute_created(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "CREATED"
    return state

def _execute_planning(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "PLANNING"
    state["current_agent"] = "ProductManagerAgent"
    # Simulate epic creation
    state["workflow_context"]["project_specs"] = "PRD draft compiled."
    # Track Metrics
    state["token_metrics"]["ProductManagerAgent"] = state["token_metrics"].get("ProductManagerAgent", 0) + 1200
    state["cost_metrics"]["ProductManagerAgent"] = state["cost_metrics"].get("ProductManagerAgent", 0.0) + 0.018
    return state

def _execute_researching(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "RESEARCHING"
    state["current_agent"] = "ResearchAgent"
    # Research report output
    state["agent_outputs"]["research_report"] = "Tech stack and versions verified."
    # Track Metrics
    state["token_metrics"]["ResearchAgent"] = state["token_metrics"].get("ResearchAgent", 0) + 2500
    state["cost_metrics"]["ResearchAgent"] = state["cost_metrics"].get("ResearchAgent", 0.0) + 0.0375
    return state

def _execute_architecting(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "ARCHITECTING"
    state["current_agent"] = "ArchitectAgent"
    state["agent_outputs"]["architecture_specs"] = "High-level design and routes mapped."
    # Track Metrics
    state["token_metrics"]["ArchitectAgent"] = state["token_metrics"].get("ArchitectAgent", 0) + 4000
    state["cost_metrics"]["ArchitectAgent"] = state["cost_metrics"].get("ArchitectAgent", 0.0) + 0.06
    return state

def _execute_db_design(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "DATABASE_DESIGN"
    state["current_agent"] = "DatabaseAgent"
    state["agent_outputs"]["ddl_script"] = "PostgreSQL schemas and indexes designed."
    # Track Metrics
    state["token_metrics"]["DatabaseAgent"] = state["token_metrics"].get("DatabaseAgent", 0) + 3000
    state["cost_metrics"]["DatabaseAgent"] = state["cost_metrics"].get("DatabaseAgent", 0.0) + 0.045
    return state

def _execute_backend_gen(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "BACKEND_GENERATION"
    state["current_agent"] = "BackendAgent"
    state["agent_outputs"]["backend_code"] = "FastAPI backend code written to tree."
    # Track Metrics
    state["token_metrics"]["BackendAgent"] = state["token_metrics"].get("BackendAgent", 0) + 12000
    state["cost_metrics"]["BackendAgent"] = state["cost_metrics"].get("BackendAgent", 0.0) + 0.18
    return state

def _execute_frontend_gen(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "FRONTEND_GENERATION"
    state["current_agent"] = "FrontendAgent"
    state["agent_outputs"]["frontend_code"] = "Next.js pages styled with Tailwind."
    # Track Metrics
    state["token_metrics"]["FrontendAgent"] = state["token_metrics"].get("FrontendAgent", 0) + 9000
    state["cost_metrics"]["FrontendAgent"] = state["cost_metrics"].get("FrontendAgent", 0.0) + 0.135
    return state

def _execute_testing(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "TESTING"
    state["current_agent"] = "QAAgent"
    # Check if QA tests should fail
    test_passed = state["workflow_context"].get("qa_force_fail", False) is False
    if test_passed:
        state["agent_outputs"]["qa_report"] = "All 8 tests passed successfully."
        state["errors"] = []
    else:
        logger.warning("QA tests failed. Flagging error for rework loop.")
        state["errors"] = state.get("errors", []) + ["Compilation error in test suite."]
    # Track Metrics
    state["token_metrics"]["QAAgent"] = state["token_metrics"].get("QAAgent", 0) + 1500
    state["cost_metrics"]["QAAgent"] = state["cost_metrics"].get("QAAgent", 0.0) + 0.0225
    return state

def _execute_security_review(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "SECURITY_REVIEW"
    state["current_agent"] = "SecurityAgent"
    state["agent_outputs"]["sast_report"] = "0 vulnerabilities detected."
    # Track Metrics
    state["token_metrics"]["SecurityAgent"] = state["token_metrics"].get("SecurityAgent", 0) + 5000
    state["cost_metrics"]["SecurityAgent"] = state["cost_metrics"].get("SecurityAgent", 0.0) + 0.075
    return state

def _execute_devops_gen(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "DEVOPS_GENERATION"
    state["current_agent"] = "DevOpsAgent"
    state["agent_outputs"]["dockerfile"] = "Dockerfile and Compose configured."
    # Track Metrics
    state["token_metrics"]["DevOpsAgent"] = state["token_metrics"].get("DevOpsAgent", 0) + 6000
    state["cost_metrics"]["DevOpsAgent"] = state["cost_metrics"].get("DevOpsAgent", 0.0) + 0.09
    return state

def _execute_approval_pending(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "APPROVAL_PENDING"
    state["current_agent"] = None
    return state

def _execute_deploying(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "DEPLOYING"
    state["current_agent"] = "DeploymentAgent"
    state["agent_outputs"]["deploy_log"] = "Rollout active: live at https://staging.codeforge.ai"
    # Track Metrics
    state["token_metrics"]["DeploymentAgent"] = state["token_metrics"].get("DeploymentAgent", 0) + 1000
    state["cost_metrics"]["DeploymentAgent"] = state["cost_metrics"].get("DeploymentAgent", 0.0) + 0.015
    return state

def _execute_observability(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "OBSERVABILITY"
    state["current_agent"] = "ObservabilityAgent"
    return state

def _execute_cost_optimization(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "COST_OPTIMIZATION"
    state["current_agent"] = "CostOptimizationAgent"
    return state

def _execute_autonomous_controller(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "AUTONOMOUS_CONTROLLER"
    state["current_agent"] = "AutonomousControllerAgent"
    return state

def _execute_final_deployment(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "FINAL_DEPLOYMENT"
    state["current_agent"] = "DevOpsAgent"
    state["agent_outputs"]["final_deployment_log"] = "Final production release deployed successfully."
    state["token_metrics"]["DevOpsAgent"] = state["token_metrics"].get("DevOpsAgent", 0) + 2000
    state["cost_metrics"]["DevOpsAgent"] = state["cost_metrics"].get("DevOpsAgent", 0.0) + 0.03
    return state

def _execute_completed(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "COMPLETED"
    state["current_agent"] = None
    return state

def _execute_failed(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "FAILED"
    state["current_agent"] = None
    return state

def _execute_cancelled(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_state"] = "CANCELLED"
    state["current_agent"] = None
    return state

# Routing conditions
def route_database_design(state: Dict[str, Any]) -> str:
    logger.warning(f"[route_database_design] agent_outputs: {list(state.get('agent_outputs', {}).keys())} | DatabaseAgent in output: {'DatabaseAgent' in state.get('agent_outputs', {})}")
    if state.get("agent_outputs", {}).get("DatabaseAgent"):
        return "BACKEND_GENERATION"
    return END

def route_backend_generation(state: Dict[str, Any]) -> str:
    if state.get("agent_outputs", {}).get("BackendAgent"):
        return "FRONTEND_GENERATION"
    return END

def route_frontend_generation(state: Dict[str, Any]) -> str:
    if state.get("agent_outputs", {}).get("FrontendAgent"):
        return "TESTING"
    return END

def route_testing_outcome(state: Dict[str, Any]) -> str:
    if not state.get("agent_outputs", {}).get("QAAgent"):
        return END
    if state.get("errors"):
        return "BACKEND_GENERATION"
    return "SECURITY_REVIEW"

def route_security_outcome(state: Dict[str, Any]) -> str:
    if state.get("agent_outputs", {}).get("SecurityAgent"):
        return "DEVOPS_GENERATION"
    return END

def route_devops_outcome(state: Dict[str, Any]) -> str:
    if state.get("agent_outputs", {}).get("DevOpsAgent"):
        return "APPROVAL_PENDING"
    return END

def route_approval_outcome(state: Dict[str, Any]) -> str:
    approved = state["workflow_context"].get("approval_status")
    if approved == "APPROVED":
        return "DEPLOYING"
    elif approved == "REJECTED":
        return "PLANNING"
    return END

def route_observability(state: Dict[str, Any]) -> str:
    if state.get("agent_outputs", {}).get("ObservabilityAgent"):
        return "COST_OPTIMIZATION"
    return END

def route_cost_optimization(state: Dict[str, Any]) -> str:
    if state.get("agent_outputs", {}).get("CostOptimizationAgent"):
        return "AUTONOMOUS_CONTROLLER"
    return END

def route_autonomous_controller(state: Dict[str, Any]) -> str:
    if state.get("agent_outputs", {}).get("AutonomousControllerAgent"):
        return "FINAL_DEPLOYMENT"
    return END

def compile_sdlc_graph() -> Any:
    """
    Constructs and compiles the 14-state LangGraph workflow graph with OpenTelemetry instrumentation.
    """
    builder = StateGraph(dict)
    
    # 1. Register Telemetry-Wrapped Nodes
    builder.add_node("CREATED", execute_node_with_telemetry("CREATED", _execute_created))
    builder.add_node("PLANNING", execute_node_with_telemetry("PLANNING", _execute_planning))
    builder.add_node("RESEARCHING", execute_node_with_telemetry("RESEARCHING", _execute_researching))
    builder.add_node("ARCHITECTING", execute_node_with_telemetry("ARCHITECTING", _execute_architecting))
    builder.add_node("DATABASE_DESIGN", execute_node_with_telemetry("DATABASE_DESIGN", _execute_db_design))
    builder.add_node("BACKEND_GENERATION", execute_node_with_telemetry("BACKEND_GENERATION", _execute_backend_gen))
    builder.add_node("FRONTEND_GENERATION", execute_node_with_telemetry("FRONTEND_GENERATION", _execute_frontend_gen))
    builder.add_node("TESTING", execute_node_with_telemetry("TESTING", _execute_testing))
    builder.add_node("SECURITY_REVIEW", execute_node_with_telemetry("SECURITY_REVIEW", _execute_security_review))
    builder.add_node("DEVOPS_GENERATION", execute_node_with_telemetry("DEVOPS_GENERATION", _execute_devops_gen))
    builder.add_node("APPROVAL_PENDING", execute_node_with_telemetry("APPROVAL_PENDING", _execute_approval_pending))
    builder.add_node("DEPLOYING", execute_node_with_telemetry("DEPLOYING", _execute_deploying))
    builder.add_node("OBSERVABILITY", execute_node_with_telemetry("OBSERVABILITY", _execute_observability))
    builder.add_node("COST_OPTIMIZATION", execute_node_with_telemetry("COST_OPTIMIZATION", _execute_cost_optimization))
    builder.add_node("AUTONOMOUS_CONTROLLER", execute_node_with_telemetry("AUTONOMOUS_CONTROLLER", _execute_autonomous_controller))
    builder.add_node("FINAL_DEPLOYMENT", execute_node_with_telemetry("FINAL_DEPLOYMENT", _execute_final_deployment))
    builder.add_node("COMPLETED", execute_node_with_telemetry("COMPLETED", _execute_completed))
    builder.add_node("FAILED", execute_node_with_telemetry("FAILED", _execute_failed))
    builder.add_node("CANCELLED", execute_node_with_telemetry("CANCELLED", _execute_cancelled))

    # 2. Add structural flow connections
    builder.set_entry_point("CREATED")
    builder.add_edge("CREATED", "PLANNING")
    builder.add_edge("PLANNING", "RESEARCHING")
    builder.add_edge("RESEARCHING", "ARCHITECTING")
    builder.add_edge("ARCHITECTING", "DATABASE_DESIGN")

    # 3. Add conditional transitions
    builder.add_conditional_edges(
        "DATABASE_DESIGN",
        route_database_design,
        {
            "BACKEND_GENERATION": "BACKEND_GENERATION",
            END: END
        }
    )

    builder.add_conditional_edges(
        "BACKEND_GENERATION",
        route_backend_generation,
        {
            "FRONTEND_GENERATION": "FRONTEND_GENERATION",
            END: END
        }
    )

    builder.add_conditional_edges(
        "FRONTEND_GENERATION",
        route_frontend_generation,
        {
            "TESTING": "TESTING",
            END: END
        }
    )

    builder.add_conditional_edges(
        "TESTING",
        route_testing_outcome,
        {
            "BACKEND_GENERATION": "BACKEND_GENERATION",
            "SECURITY_REVIEW": "SECURITY_REVIEW",
            END: END
        }
    )
    
    builder.add_conditional_edges(
        "SECURITY_REVIEW",
        route_security_outcome,
        {
            "DEVOPS_GENERATION": "DEVOPS_GENERATION",
            END: END
        }
    )

    builder.add_conditional_edges(
        "DEVOPS_GENERATION",
        route_devops_outcome,
        {
            "APPROVAL_PENDING": "APPROVAL_PENDING",
            END: END
        }
    )

    builder.add_conditional_edges(
        "APPROVAL_PENDING",
        route_approval_outcome,
        {
            "DEPLOYING": "DEPLOYING",
            "PLANNING": "PLANNING",
            END: END
        }
    )

    builder.add_edge("DEPLOYING", "OBSERVABILITY")

    builder.add_conditional_edges(
        "OBSERVABILITY",
        route_observability,
        {
            "COST_OPTIMIZATION": "COST_OPTIMIZATION",
            END: END
        }
    )

    builder.add_conditional_edges(
        "COST_OPTIMIZATION",
        route_cost_optimization,
        {
            "AUTONOMOUS_CONTROLLER": "AUTONOMOUS_CONTROLLER",
            END: END
        }
    )

    builder.add_conditional_edges(
        "AUTONOMOUS_CONTROLLER",
        route_autonomous_controller,
        {
            "FINAL_DEPLOYMENT": "FINAL_DEPLOYMENT",
            END: END
        }
    )

    builder.add_edge("FINAL_DEPLOYMENT", "COMPLETED")
    builder.add_edge("COMPLETED", END)
    builder.add_edge("FAILED", END)
    builder.add_edge("CANCELLED", END)

    return builder.compile()
