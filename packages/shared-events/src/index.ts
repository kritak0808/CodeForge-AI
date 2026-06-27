export interface BaseEvent {
  eventId: string;
  timestamp: string;
  correlationId: string;
}

export interface WorkflowEvent extends BaseEvent {
  workflowId: string;
  projectId: string;
  oldState?: string;
  newState: string;
}

export interface AgentTaskEvent extends BaseEvent {
  taskId: string;
  workflowId: string;
  agentId: string;
  command: string;
  payload: Record<string, any>;
}

export interface AgentReplyEvent extends BaseEvent {
  taskId: string;
  workflowId: string;
  agentId: string;
  status: 'SUCCESS' | 'FAILED';
  result: Record<string, any>;
}
