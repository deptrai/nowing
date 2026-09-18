"use client";
import { useTranslations } from "next-intl";
import { Switch } from "@/components/ui/switch";

interface UnattendedToggleProps {
	checked: boolean;
	onChange: (checked: boolean) => void;
}

/**
 * Maps to ``auto_approve_all`` on every agent task. Automations run with no one
 * watching, so this defaults ON; turning it off means any approval prompt the
 * agent raises is rejected and the step can stall.
 */
export function UnattendedToggle({ checked, onChange }: UnattendedToggleProps) {
	const t = useTranslations("automations");
	return (
		<div className="flex items-start justify-between gap-3 rounded-md bg-transparent">
			<div className="space-y-0.5 min-w-0">
				<div className="flex items-center gap-1.5">
					<span className="text-sm font-medium text-foreground">{t("auto_run_without_asking_for")}</span>
				</div>
				<p className="text-xs text-muted-foreground">{t("auto_tasks_run_automatically_without")}</p>
			</div>
			<Switch
				checked={checked}
				onCheckedChange={onChange}
				aria-label={t("auto_run_without_asking_for")}
			/>
		</div>
	);
}
