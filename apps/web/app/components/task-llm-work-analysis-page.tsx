import { TaskLlmWorkAnalysisView } from "./task-llm-work-analysis";


export function TaskLlmWorkAnalysisPage({ taskId }: { taskId: string }) {
  return <TaskLlmWorkAnalysisView mode="full" taskId={taskId} />;
}