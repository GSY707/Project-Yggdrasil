import { TaskLlmWorkAnalysisPage } from "../../../components/task-llm-work-analysis-page";


export default async function TaskLlmWorkAnalysisRoute({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  return <TaskLlmWorkAnalysisPage taskId={taskId} />;
}