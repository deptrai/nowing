import { useTranslations } from "next-intl";
"use client";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface AutomationNewHeaderProps {
	workspaceId: number;
	modeSwitcher?: ReactNode;
}

export function AutomationNewHeader({ workspaceId, modeSwitcher }: AutomationNewHeaderProps) {
	const t = useTranslations("automations");
	return (
		<div className="space-y-3">
			<div className="flex items-center justify-between gap-3">
				<Button asChild variant="ghost" size="sm" className="-ml-2 h-auto px-2 py-1">
					<Link
						href={`/dashboard/${workspaceId}/automations`}
						className="text-xs text-muted-foreground"
					>
						<ArrowLeft className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />{t("auto_back_to_automations")}</Link>
				</Button>
				{modeSwitcher ? <div className="shrink-0 md:hidden">{modeSwitcher}</div> : null}
			</div>

			<div className="flex items-start justify-between gap-4 flex-wrap">
				<div className="space-y-1">
					<h1 className="font-serif text-2xl sm:text-3xl font-normal text-foreground">{t("auto_new_automation")}</h1>
					<p className="text-xs sm:text-sm text-muted-foreground max-w-2xl font-sans">{t("auto_configure_the_task_schedule")}</p>
				</div>
				{modeSwitcher ? (
					<div className="ml-auto hidden shrink-0 md:block">{modeSwitcher}</div>
				) : null}
			</div>
		</div>
	);
}
