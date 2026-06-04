import { Suspense } from "react";

import { LoadingState } from "../components/workbench-primitives";
import { TasksPage } from "../components/tasks-page";

export default function TasksRoute() {
  return (
    <Suspense fallback={<LoadingState title="正在装配任务入口" />}>
      <TasksPage />
    </Suspense>
  );
}
