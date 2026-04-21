import { Suspense } from "react";

import { PromptingPage } from "../components/prompting-page";

export default function PromptingWorkbenchPage() {
  return (
    <Suspense fallback={null}>
      <PromptingPage />
    </Suspense>
  );
}