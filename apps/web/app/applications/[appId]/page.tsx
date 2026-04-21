import { ApplicationDetailPage } from "../../components/application-detail-page";

export default async function ApplicationDetailRoute({ params }: { params: Promise<{ appId: string }> }) {
  const resolved = await params;
  return <ApplicationDetailPage appId={resolved.appId} />;
}