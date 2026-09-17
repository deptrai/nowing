import { DashboardPageSkeleton } from "@/components/layout/ui/skeletons/DashboardPageSkeleton";

export default function UserSettingsLoading() {
	return <DashboardPageSkeleton titleWidthClass="w-44" showStats={false} showCharts={false} />;
}
