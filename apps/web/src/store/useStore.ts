import { create } from 'zustand';

interface Project {
  projectId: string;
  name: string;
  description?: string;
  techStack: Record<string, any>;
  budgetUsdLimit: number;
}

interface WorkflowState {
  workflowId: string;
  currentState: string;
  tasksCompleted: number;
  tasksTotal: number;
}

interface AppStore {
  projects: Project[];
  activeWorkflow: WorkflowState | null;
  currentUser: { username: string; role: string } | null;
  setProjects: (projects: Project[]) => void;
  setActiveWorkflow: (workflow: WorkflowState | null) => void;
  setCurrentUser: (user: { username: string; role: string } | null) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  projects: [],
  activeWorkflow: null,
  currentUser: null,
  setProjects: (projects) => set({ projects }),
  setActiveWorkflow: (activeWorkflow) => set({ activeWorkflow }),
  setCurrentUser: (currentUser) => set({ currentUser }),
}));
