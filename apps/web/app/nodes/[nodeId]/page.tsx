import { NodeDetailPage } from "../../components/node-detail-page";

export default async function NodeDetailRoute({ params }: { params: Promise<{ nodeId: string }> }) {
  const { nodeId } = await params;
  return <NodeDetailPage nodeId={nodeId} />;
}