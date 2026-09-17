import { DashboardPageSkeleton } from "@/components/layout/ui/skeletons/DashboardPageSkeleton";

export default function WorkspaceSettingsLoading() {
	return <DashboardPageSkeleton titleWidthClass="w-52" showStats={false} showCharts={false} />;
}
