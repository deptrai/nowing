import { DashboardPageSkeleton } from "@/components/layout/ui/skeletons/DashboardPageSkeleton";

export default function ChatsLoading() {
	return <DashboardPageSkeleton titleWidthClass="w-36" showStats={false} showCharts={false} />;
}
