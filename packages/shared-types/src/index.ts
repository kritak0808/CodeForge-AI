export interface User {
  userId: string;
  username: string;
  email: string;
  role: string;
  createdAt: string;
}

export interface Project {
  projectId: string;
  userId: string;
  name: string;
  description?: string;
  techStack: Record<string, any>;
  repositoryUrl?: string;
  budgetUsdLimit: number;
}

export interface WorkflowState {
  workflowId: string;
  projectId: string;
  currentState: 'INITIATED' | 'ARCHITECTING' | 'DEVELOPING' | 'TESTING' | 'SECURITY_AUDITING' | 'PENDING_APPROVAL' | 'DEPLOYING' | 'COMPLETED' | 'FAILED';
  triggeredBy: string;
  createdAt: string;
}
