import { useTranslations } from "next-intl";
import { DashboardPageSkeleton } from "@/components/layout/ui/skeletons/DashboardPageSkeleton";

export default function AutomationsLoading() {
	const t = useTranslations("automations");
	return <DashboardPageSkeleton titleWidthClass="w-44" />;
}
