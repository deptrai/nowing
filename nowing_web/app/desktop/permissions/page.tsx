"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useElectronAPI } from "@/hooks/use-platform";

type PermissionStatus = "authorized" | "denied" | "not determined" | "restricted" | "limited";

interface PermissionsStatus {
	accessibility: PermissionStatus;
	screenRecording: PermissionStatus;
}

function useSteps(t: ReturnType<typeof useTranslations>) {
	return [
		{
			id: "screen-recording",
			title: t("screen_recording_title"),
			description: t("screen_recording_desc"),
			action: "requestScreenRecording",
			field: "screenRecording" as const,
		},
		{
			id: "accessibility",
			title: t("accessibility_title"),
			description: t("accessibility_desc"),
			action: "requestAccessibility",
			field: "accessibility" as const,
		},
	];
}

function StatusBadge({ status }: { status: PermissionStatus }) {
	const t = useTranslations("desktopPerms");
	if (status === "authorized") {
		return (
			<span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-700 dark:text-green-400">
				<span className="h-2 w-2 rounded-full bg-green-500" />
				{t("granted")}
			</span>
		);
	}
	if (status === "denied") {
		return (
			<span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-400">
				<span className="h-2 w-2 rounded-full bg-amber-500" />
				{t("denied")}
			</span>
		);
	}
	return (
		<span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
			<span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
			{t("pending")}
		</span>
	);
}

export default function DesktopPermissionsPage() {
	const router = useRouter();
	const t = useTranslations("desktopPerms");
	const STEPS = useSteps(t);
	const api = useElectronAPI();
	const [permissions, setPermissions] = useState<PermissionsStatus | null>(null);

	useEffect(() => {
		if (!api) return;

		let interval: ReturnType<typeof setInterval> | null = null;

		const isResolved = (s: string) => s === "authorized" || s === "restricted";

		const poll = async () => {
			const status = await api.getPermissionsStatus();
			setPermissions(status);

			if (isResolved(status.accessibility) && isResolved(status.screenRecording)) {
				if (interval) clearInterval(interval);
			}
		};

		poll();
		interval = setInterval(poll, 2000);
		return () => {
			if (interval) clearInterval(interval);
		};
	}, [api]);

	if (!api) {
		return (
			<div className="h-screen flex items-center justify-center bg-background">
				<p className="text-muted-foreground">{t("desktop_only")}</p>
			</div>
		);
	}

	if (!permissions) {
		return (
			<div className="h-screen flex items-center justify-center bg-background">
				<Spinner size="lg" />
			</div>
		);
	}

	const allGranted =
		permissions.accessibility === "authorized" && permissions.screenRecording === "authorized";

	const handleRequest = async (action: string) => {
		if (action === "requestScreenRecording") {
			await api.requestScreenRecording();
		} else if (action === "requestAccessibility") {
			await api.requestAccessibility();
		}
	};

	const handleContinue = () => {
		if (allGranted) {
			api.restartApp();
		}
	};

	const handleSkip = () => {
		router.push("/dashboard");
	};

	return (
		<div className="h-screen flex flex-col items-center p-4 bg-background dark:bg-neutral-900 select-none overflow-hidden">
			<div className="w-full max-w-lg flex flex-col min-h-0 h-full gap-6 py-8">
				{/* Header */}
				<div className="text-center space-y-3 shrink-0">
					<Logo className="w-12 h-12 mx-auto" aria-hidden="true" />
					<div className="space-y-1">
						<h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
						<p className="text-sm text-muted-foreground">
							{t("subtitle")}
						</p>
					</div>
				</div>

				{/* Steps */}
				<div className="rounded-xl border bg-background dark:bg-neutral-900 flex-1 min-h-0 overflow-y-auto px-6 py-6 space-y-6">
					{STEPS.map((step, index) => {
						const status = permissions[step.field];
						const isGranted = status === "authorized";

						return (
							<div
								key={step.id}
								className={`rounded-lg border p-4 transition-colors ${
									isGranted
										? "border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20"
										: "border-border"
								}`}
							>
								<div className="flex items-start justify-between gap-3">
									<div className="flex items-start gap-3">
										<span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
											{isGranted ? "\u2713" : index + 1}
										</span>
										<div className="space-y-1">
											<h3 className="text-sm font-medium">{step.title}</h3>
											<p className="text-xs text-muted-foreground">{step.description}</p>
										</div>
									</div>
									<StatusBadge status={status} />
								</div>
								{!isGranted && (
									<div className="mt-3 pl-10 space-y-2">
										<Button
											size="sm"
											variant="outline"
											onClick={() => handleRequest(step.action)}
											className="text-xs"
										>
											{t("open_settings")}
										</Button>
										{status === "denied" && (
											<p className="text-xs text-amber-700 dark:text-amber-400">
												{t("toggle_on")}
											</p>
										)}
										<p className="text-xs text-muted-foreground">
											{t("not_in_list_1")} <strong>+</strong> {t("not_in_list_2")}
										</p>
									</div>
								)}
							</div>
						);
					})}
				</div>

				{/* Footer */}
				<div className="text-center space-y-3 shrink-0">
					{allGranted ? (
						<>
							<Button onClick={handleContinue} className="text-sm h-9 min-w-[180px]">
								{t("restart_cta")}
							</Button>
							<p className="text-xs text-muted-foreground">
								{t("restart_needed")}
							</p>
						</>
					) : (
						<>
							<Button disabled className="text-sm h-9 min-w-[180px]">
								{t("grant_cta")}
							</Button>
							<Button
								type="button"
								variant="link"
								onClick={handleSkip}
								className="mx-auto h-auto px-0 py-0 text-xs text-muted-foreground hover:text-foreground"
							>
								{t("skip")}
							</Button>
						</>
					)}
				</div>
			</div>
		</div>
	);
}
