import logging
import json
from typing import Any, Dict, List, Optional, Callable
from event_publisher import KafkaEventPublisher
from checkpoint_manager import CheckpointManager

logger = logging.getLogger("agent-orchestrator.agent-runtime")

class BaseAgentRuntime:
    def __init__(
        self,
        agent_id: str,
        event_pub: Optional[KafkaEventPublisher] = None,
        checkpoint_mgr: Optional[CheckpointManager] = None
    ):
        self.agent_id = agent_id
        self.event_pub = event_pub
        self.checkpoint_mgr = checkpoint_mgr
        self.execution_states: Dict[str, str] = {}  # Track state of each workflow run (RUNNING, PAUSED, CANCELLED)

    def execute(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a task. Should be overridden by subclasses.
        """
        logger.info(f"Agent {self.agent_id} executing task: {task_description}")
        return {
            "agent_id": self.agent_id,
            "status": "COMPLETED",
            "logs": "Execution successful.",
            "output": f"Executed task: {task_description}"
        }

    def pause(self, workflow_id: str) -> bool:
        """
        Pauses execution for a specific workflow run.
        """
        logger.info(f"Agent {self.agent_id} pausing workflow {workflow_id}")
        self.execution_states[workflow_id] = "PAUSED"
        self.publish_event("workflow.events", {
            "event_type": "AGENT_PAUSED",
            "agent_id": self.agent_id,
            "workflow_id": workflow_id
        })
        return True

    def resume(self, workflow_id: str) -> bool:
        """
        Resumes execution for a paused workflow run.
        """
        logger.info(f"Agent {self.agent_id} resuming workflow {workflow_id}")
        self.execution_states[workflow_id] = "RUNNING"
        self.publish_event("workflow.events", {
            "event_type": "AGENT_RESUMED",
            "agent_id": self.agent_id,
            "workflow_id": workflow_id
        })
        return True

    def cancel(self, workflow_id: str) -> bool:
        """
        Cancels execution for a workflow run.
        """
        logger.info(f"Agent {self.agent_id} cancelling workflow {workflow_id}")
        self.execution_states[workflow_id] = "CANCELLED"
        self.publish_event("workflow.events", {
            "event_type": "AGENT_CANCELLED",
            "agent_id": self.agent_id,
            "workflow_id": workflow_id
        })
        return True

    def checkpoint(
        self,
        workflow_id: str,
        current_node: str,
        execution_context: Dict[str, Any],
        agent_outputs: Dict[str, Any],
        errors: Optional[List[str]] = None
    ) -> Optional[int]:
        """
        Saves a checkpoint of the agent execution.
        """
        if self.checkpoint_mgr:
            logger.info(f"Agent {self.agent_id} checkpointing workflow {workflow_id} at node '{current_node}'")
            return self.checkpoint_mgr.save_checkpoint(
                workflow_id=workflow_id,
                current_node=current_node,
                execution_context=execution_context,
                agent_outputs=agent_outputs,
                errors=errors
            )
        else:
            logger.warning("Checkpoint manager not configured on this agent runtime.")
            return None

    def publish_event(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        Publishes a message to the event system.
        """
        if self.event_pub:
            return self.event_pub.publish(topic, payload)
        logger.info(f"[Mock Event Publish] Topic: {topic} | Payload: {json.dumps(payload)}")
        return True

    def consume_event(self, topic: str, group_id: str, callback: Callable[[Dict[str, Any]], None], stop_check: Optional[Callable[[], bool]] = None):
        """
        Consumes events from the event system.
        """
        if self.event_pub:
            self.event_pub.start_consumer(topic, group_id, callback, stop_check)
        else:
            logger.warning("Event publisher/consumer not configured. Skipping consume_event.")
