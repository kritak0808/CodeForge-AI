import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from state_models import WorkflowStateModel
from checkpoint_manager import CheckpointManager
from task_router import TaskRouter
from approval_handler import ApprovalHandler
from recovery_manager import RecoveryManager
from event_publisher import KafkaEventPublisher
from graph_builder import compile_sdlc_graph

logger = logging.getLogger("agent-orchestrator.workflow-manager")

class ActiveExecutionsDict(dict):
    def __init__(self, db_url):
        super().__init__()
        # Convert db_url
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif db_url.startswith("sqlite+aiosqlite://"):
            db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        self.db_url = db_url

    def __getitem__(self, key):
        if key not in self:
            self._load_from_db(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key not in self:
            self._load_from_db(key)
        return super().get(key, default)

    def _load_from_db(self, key):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models import Workflow
        import uuid
        
        try:
            uuid_val = uuid.UUID(key)
        except (ValueError, TypeError):
            self[key] = "RUNNING"
            return
            
        engine = create_engine(self.db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            wf = session.query(Workflow).filter(Workflow.workflow_id == uuid_val).first()
            if wf:
                self[key] = wf.status or "RUNNING"
            else:
                self[key] = "RUNNING"
        except Exception:
            self[key] = "RUNNING"
        finally:
            session.close()
            engine.dispose()

class WorkflowManager:
    def __init__(
        self,
        db_url: str,
        redis_url: str,
        event_pub: KafkaEventPublisher,
        max_retries: int = 3
    ):
        self.db_url = db_url
        self.redis_url = redis_url
        self.event_pub = event_pub
        
        # Instantiate sub-components
        self.checkpoint_mgr = CheckpointManager(db_url, redis_url)
        self.task_router = TaskRouter(event_pub, max_retries)
        self.approval_handler = ApprovalHandler(db_url, event_pub)
        self.recovery_mgr = RecoveryManager(db_url, self.checkpoint_mgr)
        
        # Compile LangGraph
        self.graph = compile_sdlc_graph()
        self.active_executions = ActiveExecutionsDict(db_url)  # Track runtime state (RUNNING, PAUSED, CANCELLED)


    def start_workflow(self, workflow_id: str, project_id: str, requirements: str) -> Dict[str, Any]:
        """
        Initializes a workflow state machine run and executes the first step.
        """
        logger.info(f"Starting workflow {workflow_id} for project {project_id}")
        
        initial_state = {
            "workflow_id": workflow_id,
            "project_id": project_id,
            "current_state": "CREATED",
            "current_agent": None,
            "workflow_context": {"requirements": requirements, "project_id": project_id},
            "agent_outputs": {},
            "cost_metrics": {},
            "token_metrics": {},
            "errors": []
        }

        # Save initial checkpoint
        self.checkpoint_mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node="CREATED",
            execution_context=initial_state["workflow_context"],
            agent_outputs=initial_state["agent_outputs"],
            errors=initial_state["errors"]
        )

        self.active_executions[workflow_id] = "RUNNING"
        
        # Publish start event
        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_STARTED",
            "workflow_id": workflow_id,
            "project_id": project_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Run step execution
        return self.run_workflow_step(workflow_id, initial_state)

    def run_workflow_step(self, workflow_id: str, state_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Runs the next state in the LangGraph workflow.
        """
        execution_status = self.active_executions.get(workflow_id, "RUNNING")
        if execution_status == "PAUSED":
            logger.info(f"Workflow {workflow_id} is PAUSED. Skipping execution step.")
            return {"status": "PAUSED", "workflow_id": workflow_id}
        elif execution_status == "CANCELLED":
            logger.info(f"Workflow {workflow_id} is CANCELLED. Skipping execution step.")
            return {"status": "CANCELLED", "workflow_id": workflow_id}

        # 1. Restore state from checkpoint if not provided
        if not state_input:
            checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
            if not checkpoint:
                logger.error(f"Cannot run workflow {workflow_id}: no checkpoint found.")
                return {"status": "FAILED", "error": "No checkpoint found"}
            
            state_input = {
                "workflow_id": workflow_id,
                "project_id": checkpoint.get("execution_context", {}).get("project_id", ""),
                "current_state": checkpoint.get("current_node", "CREATED"),
                "current_agent": None,
                "workflow_context": checkpoint.get("execution_context", {}),
                "agent_outputs": checkpoint.get("agent_outputs", {}),
                "cost_metrics": {},
                "token_metrics": {},
                "errors": checkpoint.get("errors", [])
            }

        current_node = state_input["current_state"]
        
        # Determine next state/node using task_router / conditional edges
        next_node = self.task_router.get_next_state(current_node, state_input["workflow_context"])
        
        # Trip circuit breaker check if we enter a loop state
        if self.recovery_mgr.check_circuit_breaker(workflow_id, next_node, state_input["workflow_context"]):
            state_input["current_state"] = "FAILED"
            state_input["errors"] = state_input.get("errors", []) + ["Circuit breaker tripped due to too many rework cycles."]
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="FAILED",
                execution_context=state_input["workflow_context"],
                agent_outputs=state_input["agent_outputs"],
                errors=state_input["errors"]
            )
            self.active_executions[workflow_id] = "FAILED"
            self.event_pub.publish("workflow.events", {
                "event_type": "WORKFLOW_FAILED",
                "workflow_id": workflow_id,
                "reason": "Circuit breaker tripped"
            })
            return state_input

        # Increment cycle count if we are looping back (e.g. back to BACKEND_GENERATION)
        if next_node == "BACKEND_GENERATION" and current_node == "TESTING":
            self.recovery_mgr.increment_rework_cycle(state_input["workflow_context"], "BACKEND_GENERATION")

        # 2. Execute graph node
        try:
            logger.info(f"Transitioning workflow {workflow_id} from {current_node} -> {next_node}")
            
            # Execute node via langgraph compiled graph dictionary mapping
            output_state = self.graph.invoke(
                {
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "current_state": next_node,
                    "current_agent": self.task_router.get_assigned_agent(next_node),
                    "workflow_context": state_input["workflow_context"],
                    "agent_outputs": state_input["agent_outputs"],
                    "cost_metrics": state_input["cost_metrics"],
                    "token_metrics": state_input["token_metrics"],
                    "errors": state_input["errors"]
                }
            )

            # Post-execution node processing
            res_state = output_state["current_state"]
            
            # Save checkpoint
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=res_state,
                execution_context=output_state["workflow_context"],
                agent_outputs=output_state["agent_outputs"],
                errors=output_state["errors"]
            )

            # Publish progressive transition event
            self.event_pub.publish("workflow.events", {
                "event_type": "WORKFLOW_STATE_CHANGED",
                "workflow_id": workflow_id,
                "previous_state": current_node,
                "current_state": res_state,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Check for terminal state nodes
            if res_state in ["COMPLETED", "FAILED", "CANCELLED"]:
                self.active_executions[workflow_id] = res_state
                self.event_pub.publish("workflow.events", {
                    "event_type": f"WORKFLOW_{res_state}",
                    "workflow_id": workflow_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
                return output_state

            # If approval required, pause and wait
            if res_state == "APPROVAL_PENDING":
                self.pause_workflow(workflow_id)
                self.approval_handler.request_approval(
                    workflow_id=workflow_id,
                    approval_type="Security",
                    artifact_payload={"dockerfiles": ["apps/web/Dockerfile"], "helm_chart": "codeforge-chart"}
                )
                return output_state

            # ── DATABASE_DESIGN gate ─────────────────────────────────────
            # Pause the graph and request the Database Agent to generate the
            # schema. The graph resumes when on_database_design_completed()
            # is called by the Kafka consumer.
            if res_state == "DATABASE_DESIGN":
                self.pause_workflow(workflow_id)
                self.event_pub.publish("database.design.requested", {
                    "event_type": "database.design.requested",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "report_id": output_state.get("agent_outputs", {})
                                                .get("ArchitectAgent", {})
                                                .get("report_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] DATABASE_DESIGN gate: published "
                    f"database.design.requested for workflow {workflow_id}"
                )
                return output_state

            # ── BACKEND_GENERATION gate ──────────────────────────────────
            # Pause the graph and request the Backend Agent to generate code.
            # The graph resumes when on_backend_generation_completed() is
            # called by the Kafka consumer.
            if res_state == "BACKEND_GENERATION":
                self.pause_workflow(workflow_id)
                self.event_pub.publish("backend.generation.requested", {
                    "event_type": "backend.generation.requested",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "design_id": output_state.get("agent_outputs", {})
                                             .get("DatabaseAgent", {})
                                             .get("design_id"),
                    "report_id": output_state.get("agent_outputs", {})
                                             .get("ArchitectAgent", {})
                                             .get("report_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] BACKEND_GENERATION gate: published "
                    f"backend.generation.requested for workflow {workflow_id}"
                )
                return output_state

            # ── FRONTEND_GENERATION gate ──────────────────────────────────
            # Pause the graph and request the Frontend Agent to generate code.
            # The graph resumes when on_frontend_generation_completed() is
            # called by the Kafka consumer.
            if res_state == "FRONTEND_GENERATION":
                self.pause_workflow(workflow_id)
                self.event_pub.publish("frontend.generation.requested", {
                    "event_type": "frontend.generation.requested",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "backend_generation_id": output_state.get("agent_outputs", {})
                                                 .get("BackendAgent", {})
                                                 .get("generation_id"),
                    "design_id": output_state.get("agent_outputs", {})
                                             .get("DatabaseAgent", {})
                                             .get("design_id"),
                    "report_id": output_state.get("agent_outputs", {})
                                             .get("ArchitectAgent", {})
                                             .get("report_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] FRONTEND_GENERATION gate: published "
                    f"frontend.generation.requested for workflow {workflow_id}"
                )
                return output_state

            # ── TESTING gate (QA Agent) ───────────────────────────────────
            # Pause the graph and request the QA Agent to generate tests.
            # The graph resumes when on_qa_generation_completed() is called.
            if res_state == "TESTING":
                self.pause_workflow(workflow_id)
                self.event_pub.publish("qa.generation.requested", {
                    "event_type": "qa.generation.requested",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "backend_generation_id": output_state.get("agent_outputs", {})
                                                 .get("BackendAgent", {})
                                                 .get("generation_id"),
                    "frontend_generation_id": output_state.get("agent_outputs", {})
                                                  .get("FrontendAgent", {})
                                                  .get("generation_id"),
                    "design_id": output_state.get("agent_outputs", {})
                                             .get("DatabaseAgent", {})
                                             .get("design_id"),
                    "report_id": output_state.get("agent_outputs", {})
                                             .get("ArchitectAgent", {})
                                             .get("report_id"),
                    "qa_force_fail": output_state.get("workflow_context", {}).get("qa_force_fail", False),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] TESTING gate: published "
                    f"qa.generation.requested for workflow {workflow_id}"
                )
                return output_state

            # ── SECURITY_REVIEW gate (Security Agent) ─────────────────────
            # Pause the graph and request the Security Agent to assess safety.
            # The graph resumes when on_security_generation_completed() is called.
            if res_state == "SECURITY_REVIEW":
                self.pause_workflow(workflow_id)
                self.event_pub.publish("security.generation.requested", {
                    "event_type": "security.generation.requested",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "backend_generation_id": output_state.get("agent_outputs", {})
                                                 .get("BackendAgent", {})
                                                 .get("generation_id"),
                    "frontend_generation_id": output_state.get("agent_outputs", {})
                                                   .get("FrontendAgent", {})
                                                   .get("generation_id"),
                    "design_id": output_state.get("agent_outputs", {})
                                             .get("DatabaseAgent", {})
                                             .get("design_id"),
                    "report_id": output_state.get("agent_outputs", {})
                                             .get("ArchitectAgent", {})
                                             .get("report_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] SECURITY_REVIEW gate: published "
                    f"security.generation.requested for workflow {workflow_id}"
                )
                return output_state

            # ── DEVOPS_GENERATION gate (DevOps Agent) ─────────────────────
            # Pause the graph and request the DevOps Agent to compile cloud templates.
            # The graph resumes when on_devops_generation_completed() is called.
            if res_state == "DEVOPS_GENERATION":
                self.pause_workflow(workflow_id)
                self.event_pub.publish("devops.generation.requested", {
                    "event_type": "devops.generation.requested",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "backend_generation_id": output_state.get("agent_outputs", {})
                                                 .get("BackendAgent", {})
                                                 .get("generation_id"),
                    "frontend_generation_id": output_state.get("agent_outputs", {})
                                                   .get("FrontendAgent", {})
                                                   .get("generation_id"),
                    "design_id": output_state.get("agent_outputs", {})
                                             .get("DatabaseAgent", {})
                                             .get("design_id"),
                    "report_id": output_state.get("agent_outputs", {})
                                             .get("ArchitectAgent", {})
                                             .get("report_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] DEVOPS_GENERATION gate: published "
                    f"devops.generation.requested for workflow {workflow_id}"
                )
                return output_state

            # ── OBSERVABILITY gate (Observability Agent) ──────────────────
            if res_state == "OBSERVABILITY":
                self.pause_workflow(workflow_id)
                self.event_pub.publish("observability.started", {
                    "event_type": "observability.started",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] OBSERVABILITY gate: published "
                    f"observability.started for workflow {workflow_id}"
                )
                return output_state

            # ── COST_OPTIMIZATION gate (Cost Optimization Agent) ──────────
            if res_state == "COST_OPTIMIZATION":
                self.pause_workflow(workflow_id)
                self.event_pub.publish("cost.started", {
                    "event_type": "cost.started",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] COST_OPTIMIZATION gate: published "
                    f"cost.started for workflow {workflow_id}"
                )
                return output_state

            # ── AUTONOMOUS_CONTROLLER gate (Autonomous SDLC Controller Agent) ──
            if res_state == "AUTONOMOUS_CONTROLLER":
                self.pause_workflow(workflow_id)
                errors_list = output_state.get("errors", [])
                accumulated_cost = sum(output_state.get("cost_metrics", {}).values())
                self.event_pub.publish("controller.started", {
                    "event_type": "controller.started",
                    "workflow_id": workflow_id,
                    "project_id": state_input["project_id"],
                    "current_step": "AUTONOMOUS_CONTROLLER",
                    "errors": errors_list,
                    "metrics": {
                        "cpu_utilization": 22.0,
                        "memory_utilization": 45.0,
                    },
                    "budget_limit": 1000.0,
                    "accumulated_cost": accumulated_cost,
                    "retry_attempt": output_state.get("workflow_context", {}).get("retry_attempt", 1),
                    "agent_heartbeats": {"ResearchAgent": "OK", "DatabaseAgent": "OK", "CostOptimizationAgent": "OK"},
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.info(
                    f"[WorkflowManager] AUTONOMOUS_CONTROLLER gate: published "
                    f"controller.started for workflow {workflow_id}"
                )
                return output_state

            # Otherwise, keep running the next steps asynchronously or synchronously in series
            return self.run_workflow_step(workflow_id, output_state)


        except Exception as e:
            logger.error(f"Execution error on workflow {workflow_id}: {e}")
            state_input["current_state"] = "FAILED"
            state_input["errors"] = state_input.get("errors", []) + [str(e)]
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="FAILED",
                execution_context=state_input["workflow_context"],
                agent_outputs=state_input["agent_outputs"],
                errors=state_input["errors"]
            )
            self.active_executions[workflow_id] = "FAILED"
            self.event_pub.publish("workflow.errors", {
                "workflow_id": workflow_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            return state_input

    def _update_db_workflow_status(self, workflow_id: str, status: str) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models import Workflow
        import uuid

        db_url = self.db_url
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif db_url.startswith("sqlite+aiosqlite://"):
            db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)

        try:
            uuid_val = uuid.UUID(workflow_id)
        except (ValueError, TypeError):
            return

        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            wf = session.query(Workflow).filter(Workflow.workflow_id == uuid_val).first()
            if wf:
                wf.status = status
                session.commit()
                logger.info(f"Updated workflow {workflow_id} database status to {status}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating workflow status in DB: {e}")
        finally:
            session.close()
            engine.dispose()

    def pause_workflow(self, workflow_id: str) -> bool:
        logger.info(f"Pausing execution of workflow: {workflow_id}")
        self.active_executions[workflow_id] = "PAUSED"
        self._update_db_workflow_status(workflow_id, "PAUSED")
        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_PAUSED",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        return True

    def resume_workflow(self, workflow_id: str) -> bool:
        logger.info(f"Resuming execution of workflow: {workflow_id}")
        self.active_executions[workflow_id] = "RUNNING"
        self._update_db_workflow_status(workflow_id, "RUNNING")
        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Trigger next step execution in separate thread or loop
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            self.run_workflow_step(workflow_id)
            return True
        return False

    def cancel_workflow(self, workflow_id: str) -> bool:
        logger.info(f"Cancelling execution of workflow: {workflow_id}")
        self.active_executions[workflow_id] = "CANCELLED"
        
        # Save cancellation node checkpoint
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        execution_ctx = checkpoint.get("execution_context", {}) if checkpoint else {}
        agent_outs = checkpoint.get("agent_outputs", {}) if checkpoint else {}
        
        self.checkpoint_mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node="CANCELLED",
            execution_context=execution_ctx,
            agent_outputs=agent_outs,
            errors=["Cancelled by operator."]
        )
        
        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_CANCELLED",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        return True

    def recover_workflow(self, workflow_id: str) -> bool:
        """
        Manually triggers recovery of an interrupted workflow from its latest checkpoint.
        """
        logger.info(f"Running manual recovery checklist for workflow {workflow_id}")
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if not checkpoint:
            logger.warning(f"Recovery failed: No checkpoint found for workflow {workflow_id}")
            return False

        last_node = checkpoint.get("current_node", "CREATED")
        logger.info(f"Recovered workflow {workflow_id} at node '{last_node}'")
        
        self.active_executions[workflow_id] = "RUNNING"
        self.run_workflow_step(workflow_id)
        return True

    # ────────────────────────────────────────────────────────────────────
    # MILESTONE 7 – Database Agent Kafka Event Callbacks
    # ────────────────────────────────────────────────────────────────────

    def on_database_design_completed(
        self,
        workflow_id: str,
        design_id: str,
        result_summary: dict | None = None,
    ) -> bool:
        """
        Called by the Kafka consumer when 'database.design.completed' is received.

        Resumes the workflow and transitions it from DATABASE_DESIGN to
        APPROVAL_PENDING (a Database approval gate is created by the service).
        """
        logger.info(
            f"[WorkflowManager] database.design.completed received: "
            f"workflow_id={workflow_id} design_id={design_id}"
        )

        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received database.design.completed for workflow "
                f"{workflow_id} but it is not PAUSED (state="
                f"{self.active_executions.get(workflow_id)}). Ignoring."
            )
            return False

        # Resume execution – the graph will advance past DATABASE_DESIGN
        self.active_executions[workflow_id] = "RUNNING"

        # Update checkpoint to reflect the agent completion
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            ctx["database_design_id"] = design_id
            ctx["database_design_summary"] = result_summary or {}
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="DATABASE_DESIGN",
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "DatabaseAgent": {"design_id": design_id, **(result_summary or {})},
                },
                errors=checkpoint.get("errors", []),
            )

        # Publish state transition and continue graph execution
        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "database.design.completed",
            "design_id": design_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.run_workflow_step(workflow_id)
        return True

    def on_database_design_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called by the Kafka consumer when 'database.design.failed' is received.

        Transitions the workflow to FAILED state and publishes an alert.
        """
        logger.error(
            f"[WorkflowManager] database.design.failed received: "
            f"workflow_id={workflow_id} error={error}"
        )

        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        ctx = checkpoint.get("execution_context", {}) if checkpoint else {}
        outs = checkpoint.get("agent_outputs", {}) if checkpoint else {}

        self.checkpoint_mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node="FAILED",
            execution_context=ctx,
            agent_outputs=outs,
            errors=[f"DatabaseAgent failed: {error}"],
        )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "workflow_id": workflow_id,
            "reason": f"Database Agent pipeline failed: {error}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.event_pub.publish("workflow.errors", {
            "workflow_id": workflow_id,
            "error": f"Database design generation failed: {error}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        return True

    # ────────────────────────────────────────────────────────────────────
    # MILESTONE 8 – Backend Agent Kafka Event Callbacks
    # ────────────────────────────────────────────────────────────────────

    def on_backend_generation_completed(
        self,
        workflow_id: str,
        generation_id: str,
        result_summary: dict | None = None,
    ) -> bool:
        """
        Called by the Kafka consumer when 'backend.generation.completed' is received.

        Resumes the workflow and transitions it from BACKEND_GENERATION to
        BACKEND_REVIEW (a Backend approval gate is created by the service).
        """
        logger.info(
            f"[WorkflowManager] backend.generation.completed received: "
            f"workflow_id={workflow_id} generation_id={generation_id}"
        )

        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received backend.generation.completed for workflow "
                f"{workflow_id} but it is not PAUSED (state="
                f"{self.active_executions.get(workflow_id)}). Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        # Update checkpoint to include generation artifact reference
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            ctx["backend_generation_id"] = generation_id
            ctx["backend_generation_summary"] = result_summary or {}
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="BACKEND_GENERATION",
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "BackendAgent": {
                        "generation_id": generation_id,
                        **(result_summary or {}),
                    },
                },
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "backend.generation.completed",
            "generation_id": generation_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.run_workflow_step(workflow_id)
        return True

    def on_backend_generation_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called by the Kafka consumer when 'backend.generation.failed' is received.

        Transitions the workflow to FAILED state and publishes an alert.
        """
        logger.error(
            f"[WorkflowManager] backend.generation.failed received: "
            f"workflow_id={workflow_id} error={error}"
        )

        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        ctx = checkpoint.get("execution_context", {}) if checkpoint else {}
        outs = checkpoint.get("agent_outputs", {}) if checkpoint else {}

        self.checkpoint_mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node="FAILED",
            execution_context=ctx,
            agent_outputs=outs,
            errors=[f"BackendAgent failed: {error}"],
        )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "workflow_id": workflow_id,
            "reason": f"Backend Agent pipeline failed: {error}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.event_pub.publish("workflow.errors", {
            "workflow_id": workflow_id,
            "error": f"Backend code generation failed: {error}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        return True

    # ────────────────────────────────────────────────────────────────────
    # MILESTONE 9 – Frontend Agent Kafka Event Callbacks
    # ────────────────────────────────────────────────────────────────────

    def on_frontend_generation_completed(
        self,
        workflow_id: str,
        generation_id: str,
        result_summary: dict | None = None,
    ) -> bool:
        """
        Called by the Kafka consumer when 'frontend.generation.completed' is received.
        Resumes the workflow and transitions it to the next step. Also publishes
        frontend.review.requested event.
        """
        logger.info(
            f"[WorkflowManager] frontend.generation.completed received: "
            f"workflow_id={workflow_id} generation_id={generation_id}"
        )

        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received frontend.generation.completed for workflow "
                f"{workflow_id} but it is not PAUSED (state="
                f"{self.active_executions.get(workflow_id)}). Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        # Update checkpoint to include frontend generation artifact reference
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        project_id = None
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            project_id = ctx.get("project_id")
            ctx["frontend_generation_id"] = generation_id
            ctx["frontend_generation_summary"] = result_summary or {}
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="FRONTEND_GENERATION",
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "FrontendAgent": {
                        "generation_id": generation_id,
                        **(result_summary or {}),
                    },
                },
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "frontend.generation.completed",
            "generation_id": generation_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Publish frontend review requested event as specified
        self.event_pub.publish("frontend.review.requested", {
            "event_type": "frontend.review.requested",
            "generation_id": generation_id,
            "workflow_id": workflow_id,
            "project_id": project_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info(f"[WorkflowManager] published frontend.review.requested for generation {generation_id}")

        self.run_workflow_step(workflow_id)
        return True

    def on_frontend_generation_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called by the Kafka consumer when 'frontend.generation.failed' is received.
        Transitions the workflow to FAILED state and publishes an alert.
        """
        logger.error(
            f"[WorkflowManager] frontend.generation.failed received: "
            f"workflow_id={workflow_id} error={error}"
        )

        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        ctx = checkpoint.get("execution_context", {}) if checkpoint else {}
        outs = checkpoint.get("agent_outputs", {}) if checkpoint else {}

        self.checkpoint_mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node="FAILED",
            execution_context=ctx,
            agent_outputs=outs,
            errors=[f"FrontendAgent failed: {error}"],
        )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "reason": f"Frontend Agent pipeline failed: {error}",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.event_pub.publish("workflow.errors", {
            "workflow_id": workflow_id,
            "error": f"Frontend code generation failed: {error}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        return True

    # ────────────────────────────────────────────────────────────────────
    # MILESTONE 10 – QA Agent Kafka Event Callbacks
    # ────────────────────────────────────────────────────────────────────

    def on_qa_generation_completed(
        self,
        workflow_id: str,
        generation_id: str,
        result_summary: dict | None = None,
        errors: list | None = None,
    ) -> bool:
        """
        Called by the Kafka consumer when 'qa.generation.completed' is received.
        Resumes the workflow and transitions it to the next step. Also publishes
        qa.review.requested event.
        """
        logger.info(
            f"[WorkflowManager] qa.generation.completed received: "
            f"workflow_id={workflow_id} generation_id={generation_id}"
        )

        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received qa.generation.completed for workflow "
                f"{workflow_id} but it is not PAUSED (state="
                f"{self.active_executions.get(workflow_id)}). Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        # Update checkpoint to include QA generation artifact reference
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        project_id = None
        ctx = {}
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            project_id = ctx.get("project_id")
            ctx["qa_generation_id"] = generation_id
            ctx["qa_generation_summary"] = result_summary or {}

            # If bugs/errors were detected (e.g. forced fail), flag them in context errors
            if errors:
                ctx["errors"] = (ctx.get("errors", []) or []) + errors
                checkpoint["errors"] = (checkpoint.get("errors", []) or []) + errors
            else:
                ctx["errors"] = []
                checkpoint["errors"] = []

            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="TESTING",
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "QAAgent": {
                        "generation_id": generation_id,
                        **(result_summary or {}),
                    },
                },
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "qa.generation.completed",
            "generation_id": generation_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Publish QA review requested event as specified
        self.event_pub.publish("qa.review.requested", {
            "event_type": "qa.review.requested",
            "generation_id": generation_id,
            "workflow_id": workflow_id,
            "project_id": project_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info(f"[WorkflowManager] published qa.review.requested for generation {generation_id}")

        self.run_workflow_step(workflow_id)
        return True

    def on_qa_generation_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called by the Kafka consumer when 'qa.generation.failed' is received.
        Transitions the workflow to FAILED state and publishes an alert.
        """
        logger.error(
            f"[WorkflowManager] qa.generation.failed received: "
            f"workflow_id={workflow_id} error={error}"
        )

        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        ctx = checkpoint.get("execution_context", {}) if checkpoint else {}
        outs = checkpoint.get("agent_outputs", {}) if checkpoint else {}

        self.checkpoint_mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node="FAILED",
            execution_context=ctx,
            agent_outputs=outs,
            errors=[f"QAAgent failed: {error}"],
        )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "reason": f"QA Agent pipeline failed: {error}",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.event_pub.publish("workflow.errors", {
            "workflow_id": workflow_id,
            "error": f"QA code generation failed: {error}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        return True

    # ────────────────────────────────────────────────────────────────────
    # MILESTONE 11 – Security Agent Kafka Event Callbacks
    # ────────────────────────────────────────────────────────────────────

    def on_security_generation_completed(
        self,
        workflow_id: str,
        generation_id: str,
        result_summary: dict | None = None,
    ) -> bool:
        """
        Called by the Kafka consumer when 'security.generation.completed' is received.
        Resumes the workflow and transitions it to the next step. Also publishes
        security.review.requested event.
        """
        logger.info(
            f"[WorkflowManager] security.generation.completed received: "
            f"workflow_id={workflow_id} generation_id={generation_id}"
        )

        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received security.generation.completed for workflow "
                f"{workflow_id} but it is not PAUSED (state="
                f"{self.active_executions.get(workflow_id)}). Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        # Update checkpoint to include Security generation artifact reference
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        project_id = None
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            project_id = ctx.get("project_id")
            ctx["security_generation_id"] = generation_id
            ctx["security_generation_summary"] = result_summary or {}
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="SECURITY_REVIEW",
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "SecurityAgent": {
                        "generation_id": generation_id,
                        **(result_summary or {}),
                    },
                },
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "security.generation.completed",
            "generation_id": generation_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Publish security review requested event as specified
        self.event_pub.publish("security.review.requested", {
            "event_type": "security.review.requested",
            "generation_id": generation_id,
            "workflow_id": workflow_id,
            "project_id": project_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info(f"[WorkflowManager] published security.review.requested for generation {generation_id}")

        self.run_workflow_step(workflow_id)
        return True

    def on_security_generation_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called by the Kafka consumer when 'security.generation.failed' is received.
        Transitions the workflow to FAILED state and publishes an alert.
        """
        logger.error(
            f"[WorkflowManager] security.generation.failed received: "
            f"workflow_id={workflow_id} error={error}"
        )

        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        ctx = checkpoint.get("execution_context", {}) if checkpoint else {}
        outs = checkpoint.get("agent_outputs", {}) if checkpoint else {}

        self.checkpoint_mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node="FAILED",
            execution_context=ctx,
            agent_outputs=outs,
            errors=[f"SecurityAgent failed: {error}"],
        )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "reason": f"Security Agent pipeline failed: {error}",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.event_pub.publish("workflow.errors", {
            "workflow_id": workflow_id,
            "error": f"Security review failed: {error}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        return True

    # ────────────────────────────────────────────────────────────────────
    # MILESTONE 12 – DevOps Agent Kafka Event Callbacks
    # ────────────────────────────────────────────────────────────────────

    def on_devops_generation_completed(
        self,
        workflow_id: str,
        generation_id: str,
        result_summary: dict | None = None,
    ) -> bool:
        """
        Called by the Kafka consumer when 'devops.generation.completed' is received.
        Resumes the workflow and transitions it to the next step. Also publishes
        devops.review.requested event.
        """
        logger.info(
            f"[WorkflowManager] devops.generation.completed received: "
            f"workflow_id={workflow_id} generation_id={generation_id}"
        )

        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received devops.generation.completed for workflow "
                f"{workflow_id} but it is not PAUSED (state="
                f"{self.active_executions.get(workflow_id)}). Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        # Update checkpoint to include DevOps generation artifact reference
        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        project_id = None
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            project_id = ctx.get("project_id")
            ctx["devops_generation_id"] = generation_id
            ctx["devops_generation_summary"] = result_summary or {}
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="DEVOPS_GENERATION",
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "DevOpsAgent": {
                        "generation_id": generation_id,
                        **(result_summary or {}),
                    },
                },
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "devops.generation.completed",
            "generation_id": generation_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Publish devops review requested event as specified
        self.event_pub.publish("devops.review.requested", {
            "event_type": "devops.review.requested",
            "generation_id": generation_id,
            "workflow_id": workflow_id,
            "project_id": project_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info(f"[WorkflowManager] published devops.review.requested for generation {generation_id}")

        self.run_workflow_step(workflow_id)
        return True

    def on_devops_generation_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called by the Kafka consumer when 'devops.generation.failed' is received.
        Transitions the workflow to FAILED state and publishes an alert.
        """
        logger.error(
            f"[WorkflowManager] devops.generation.failed received: "
            f"workflow_id={workflow_id} error={error}"
        )

        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        ctx = checkpoint.get("execution_context", {}) if checkpoint else {}
        outs = checkpoint.get("agent_outputs", {}) if checkpoint else {}

        self.checkpoint_mgr.save_checkpoint(
            workflow_id=workflow_id,
            current_node="FAILED",
            execution_context=ctx,
            agent_outputs=outs,
            errors=[f"DevOpsAgent failed: {error}"],
        )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "reason": f"DevOps Agent pipeline failed: {error}",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.event_pub.publish("workflow.errors", {
            "workflow_id": workflow_id,
            "error": f"DevOps template generation failed: {error}",
            "timestamp": datetime.utcnow().isoformat(),
        })

        return True

    def _get_workflow_id_by_session_id(self, session_id: str) -> Optional[str]:
        from app.models import AgentCollaborationSession
        db_session = self.checkpoint_mgr.SessionLocal()
        try:
            session = db_session.query(AgentCollaborationSession).filter(
                AgentCollaborationSession.session_id == uuid.UUID(session_id)
            ).first()
            if session:
                return str(session.workflow_id)
            return None
        except Exception as e:
            logger.error(f"Error querying workflow_id for session_id {session_id}: {e}")
            return None
        finally:
            db_session.close()

    def on_agent_review_requested(
        self,
        session_id: str,
        review_id: str,
        reviewer_agent: str,
        target_agent: str,
        artifact_type: str,
        artifact_id: str,
    ) -> bool:
        logger.info(
            f"[WorkflowManager] on_agent_review_requested received: "
            f"session_id={session_id} review_id={review_id} reviewer={reviewer_agent}"
        )
        workflow_id = self._get_workflow_id_by_session_id(session_id)
        if not workflow_id:
            logger.warning(f"[WorkflowManager] No workflow_id found for session_id={session_id}")
            return False

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            collaboration = ctx.setdefault("collaboration", {})
            reviews = collaboration.setdefault("reviews", {})
            reviews[review_id] = {
                "reviewer_agent": reviewer_agent,
                "target_agent": target_agent,
                "artifact_type": artifact_type,
                "artifact_id": artifact_id,
                "status": "PENDING",
                "requested_at": datetime.utcnow().isoformat(),
            }
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=checkpoint.get("errors", []),
            )
            return True
        return False

    def on_agent_review_completed(
        self,
        session_id: str,
        review_id: str,
        reviewer_agent: str,
        status: str,
    ) -> bool:
        logger.info(
            f"[WorkflowManager] on_agent_review_completed received: "
            f"session_id={session_id} review_id={review_id} status={status}"
        )
        workflow_id = self._get_workflow_id_by_session_id(session_id)
        if not workflow_id:
            logger.warning(f"[WorkflowManager] No workflow_id found for session_id={session_id}")
            return False

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            collaboration = ctx.setdefault("collaboration", {})
            reviews = collaboration.setdefault("reviews", {})
            review_item = reviews.setdefault(review_id, {})
            review_item["status"] = status
            review_item["completed_at"] = datetime.utcnow().isoformat()
            
            if status == "REWORK_REQUESTED":
                checkpoint["errors"] = checkpoint.get("errors", []) + [f"Review {review_id} requested rework."]
                ctx["errors"] = ctx.get("errors", []) + [f"Review {review_id} requested rework."]

            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=checkpoint.get("errors", []),
            )
            return True
        return False

    def on_agent_vote_completed(
        self,
        session_id: str,
        topic: str,
        voter_agent: str,
        decision: str,
    ) -> bool:
        logger.info(
            f"[WorkflowManager] on_agent_vote_completed received: "
            f"session_id={session_id} topic={topic} voter={voter_agent} decision={decision}"
        )
        workflow_id = self._get_workflow_id_by_session_id(session_id)
        if not workflow_id:
            logger.warning(f"[WorkflowManager] No workflow_id found for session_id={session_id}")
            return False

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            collaboration = ctx.setdefault("collaboration", {})
            votes = collaboration.setdefault("votes", {})
            topic_votes = votes.setdefault(topic, {})
            topic_votes[voter_agent] = decision
            
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=checkpoint.get("errors", []),
            )
            return True
        return False

    def on_agent_conflict_resolved(
        self,
        session_id: str,
        conflict_id: str,
        resolved_by: str,
        strategy: str,
    ) -> bool:
        logger.info(
            f"[WorkflowManager] on_agent_conflict_resolved received: "
            f"session_id={session_id} conflict_id={conflict_id} resolved_by={resolved_by} strategy={strategy}"
        )
        workflow_id = self._get_workflow_id_by_session_id(session_id)
        if not workflow_id:
            logger.warning(f"[WorkflowManager] No workflow_id found for session_id={session_id}")
            return False

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            collaboration = ctx.setdefault("collaboration", {})
            conflicts = collaboration.setdefault("conflicts", {})
            conflicts[conflict_id] = {
                "status": "RESOLVED",
                "resolved_by": resolved_by,
                "strategy": strategy,
                "resolved_at": datetime.utcnow().isoformat(),
            }
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=checkpoint.get("errors", []),
            )
            return True
        return False

    def on_agent_collaboration_completed(
        self,
        workflow_id: str,
        session_id: str,
    ) -> bool:
        logger.info(
            f"[WorkflowManager] on_agent_collaboration_completed received: "
            f"workflow_id={workflow_id} session_id={session_id}"
        )
        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received agent.collaboration.completed for workflow "
                f"{workflow_id} but it is not PAUSED. Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            ctx["collaboration_session_id"] = session_id
            ctx["collaboration_status"] = "COMPLETED"
            
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "CollaborationSession": {"session_id": session_id, "status": "COMPLETED"},
                },
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "agent.collaboration.completed",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.run_workflow_step(workflow_id)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # MILESTONE 15 – Observability & Monitoring Platform Callbacks
    # ─────────────────────────────────────────────────────────────────────────

    def on_observability_completed(
        self,
        workflow_id: str,
        generation_id: str,
        result_summary: dict,
    ) -> bool:
        """
        Called when observability.completed arrives from the agent worker.
        Restores checkpoint, records the generation_id, publishes a review
        request, and resumes the workflow state machine.
        """
        logger.info(
            f"[WorkflowManager] on_observability_completed: "
            f"workflow_id={workflow_id} generation_id={generation_id}"
        )
        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received observability.completed for workflow "
                f"{workflow_id} but it is not PAUSED. Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            ctx["observability_generation_id"] = generation_id
            ctx["observability_status"] = "COMPLETED"

            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "ObservabilityAgent": {
                        "generation_id": generation_id,
                        **result_summary,
                    },
                },
                errors=checkpoint.get("errors", []),
            )

        # Notify downstream consumers
        self.event_pub.publish("observability.review.requested", {
            "event_type": "observability.review.requested",
            "workflow_id": workflow_id,
            "generation_id": generation_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.run_workflow_step(workflow_id)
        return True

    def on_observability_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called when observability.generation.failed arrives.
        Transitions the workflow to FAILED state and publishes an error event.
        """
        logger.error(
            f"[WorkflowManager] on_observability_failed: "
            f"workflow_id={workflow_id} error={error}"
        )
        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            errors = checkpoint.get("errors", [])
            errors.append({"stage": "OBSERVABILITY_GENERATION", "error": error})
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=errors,
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "workflow_id": workflow_id,
            "stage": "OBSERVABILITY_GENERATION",
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True


    # ─────────────────────────────────────────────────────────────────────────
    # MILESTONE 16 – Cost Optimization Callbacks
    # ─────────────────────────────────────────────────────────────────────────

    def on_cost_analysis_completed(
        self,
        workflow_id: str,
        generation_id: str,
        result_summary: dict,
    ) -> bool:
        """
        Called when cost.analysis.completed arrives from the agent worker.
        Restores checkpoint, records the generation_id, and resumes the workflow.
        """
        logger.info(
            f"[WorkflowManager] on_cost_analysis_completed: "
            f"workflow_id={workflow_id} generation_id={generation_id}"
        )
        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received cost.analysis.completed for workflow "
                f"{workflow_id} but it is not PAUSED. Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            ctx["cost_generation_id"] = generation_id
            ctx["cost_status"] = "COMPLETED"

            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "CostOptimizationAgent": {
                        "generation_id": generation_id,
                        **result_summary,
                    },
                },
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "cost.analysis.completed",
            "generation_id": generation_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.run_workflow_step(workflow_id)
        return True

    def on_cost_analysis_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called when cost.analysis.failed arrives.
        Transitions the workflow to FAILED state and publishes an error event.
        """
        logger.error(
            f"[WorkflowManager] on_cost_analysis_failed: "
            f"workflow_id={workflow_id} error={error}"
        )
        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            errors = checkpoint.get("errors", [])
            errors.append({"stage": "COST_OPTIMIZATION", "error": error})
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="FAILED",
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=errors,
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "workflow_id": workflow_id,
            "stage": "COST_OPTIMIZATION",
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True


    # ─────────────────────────────────────────────────────────────────────────
    # MILESTONE 17 – Autonomous Controller Callbacks
    # ─────────────────────────────────────────────────────────────────────────

    def on_controller_completed(
        self,
        workflow_id: str,
        controller_id: str,
        result_summary: Optional[dict] = None,
    ) -> bool:
        """
        Called when controller.completed arrives.
        Resumes the workflow and moves to the next node (FINAL_DEPLOYMENT).
        """
        logger.info(
            f"[WorkflowManager] on_controller_completed: "
            f"workflow_id={workflow_id} controller_id={controller_id}"
        )
        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received controller.completed for workflow "
                f"{workflow_id} but it is not PAUSED. Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            ctx["controller_id"] = controller_id
            ctx["controller_status"] = "COMPLETED"

            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=checkpoint.get("current_node"),
                execution_context=ctx,
                agent_outputs={
                    **checkpoint.get("agent_outputs", {}),
                    "AutonomousControllerAgent": {
                        "controller_id": controller_id,
                        **(result_summary or {}),
                    },
                },
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "controller.completed",
            "controller_id": controller_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.run_workflow_step(workflow_id)
        return True

    def on_controller_retry(
        self,
        workflow_id: str,
        controller_id: str,
        step: str,
        retry_attempt: int,
    ) -> bool:
        """
        Called when controller.retry arrives.
        Resets the current node to the targeted retry step, increments retry attempt,
        resumes the workflow from that node.
        """
        logger.info(
            f"[WorkflowManager] on_controller_retry: workflow_id={workflow_id} "
            f"controller_id={controller_id} step={step} attempt={retry_attempt}"
        )
        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received controller.retry for workflow "
                f"{workflow_id} but it is not PAUSED. Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            ctx["retry_attempt"] = retry_attempt
            ctx["last_retry_step"] = step

            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=step,
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=checkpoint.get("errors", []),
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "controller.retry",
            "retry_step": step,
            "retry_attempt": retry_attempt,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.run_workflow_step(workflow_id)
        return True

    def on_controller_rollback(
        self,
        workflow_id: str,
        controller_id: str,
        source_step: str,
        target_step: str,
    ) -> bool:
        """
        Called when controller.rollback arrives.
        Resets the workflow back to the target rollback node, clearing errors.
        """
        logger.info(
            f"[WorkflowManager] on_controller_rollback: workflow_id={workflow_id} "
            f"controller_id={controller_id} source={source_step} target={target_step}"
        )
        if self.active_executions.get(workflow_id) != "PAUSED":
            logger.warning(
                f"[WorkflowManager] Received controller.rollback for workflow "
                f"{workflow_id} but it is not PAUSED. Ignoring."
            )
            return False

        self.active_executions[workflow_id] = "RUNNING"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            ctx["last_rollback_from"] = source_step
            ctx["last_rollback_to"] = target_step
            errors = []

            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=target_step,
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=errors,
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_RESUMED",
            "workflow_id": workflow_id,
            "trigger": "controller.rollback",
            "target_step": target_step,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.run_workflow_step(workflow_id)
        return True

    def on_controller_failed(
        self,
        workflow_id: str,
        error: str,
    ) -> bool:
        """
        Called when controller.failed arrives.
        Fails the workflow.
        """
        logger.error(
            f"[WorkflowManager] on_controller_failed: "
            f"workflow_id={workflow_id} error={error}"
        )
        self.active_executions[workflow_id] = "FAILED"

        checkpoint = self.checkpoint_mgr.restore_checkpoint(workflow_id)
        if checkpoint:
            ctx = checkpoint.get("execution_context", {})
            errors = checkpoint.get("errors", [])
            errors.append({"stage": "AUTONOMOUS_CONTROLLER", "error": error})
            self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node="FAILED",
                execution_context=ctx,
                agent_outputs=checkpoint.get("agent_outputs", {}),
                errors=errors,
            )

        self.event_pub.publish("workflow.events", {
            "event_type": "WORKFLOW_FAILED",
            "workflow_id": workflow_id,
            "stage": "AUTONOMOUS_CONTROLLER",
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True
