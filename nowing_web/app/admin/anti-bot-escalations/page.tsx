"use client";

import { useAtom } from "jotai";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
	type AntiBotEscalation,
	antiBotEscalationsApiService,
} from "@/lib/apis/anti-bot-escalations-api.service";
import { BACKEND_URL } from "@/lib/env-config";

function isAccessError(error: unknown): boolean {
	return (
		typeof error === "object" &&
		error !== null &&
		"status" in error &&
		(error as { status?: number }).status === 403
	);
}

export default function AntiBotEscalationsAdminPage() {
	const t = useTranslations("admin");
	const [{ isLoading: userLoading }] = useAtom(currentUserAtom);
	const [escalations, setEscalations] = useState<AntiBotEscalation[]>([]);
	const [loading, setLoading] = useState(true);

	const [accessDenied, setAccessDenied] = useState(false);

	const load = useCallback(async () => {
		setLoading(true);
		setAccessDenied(false);
		try {
			const data = await antiBotEscalationsApiService.list();
			setEscalations(data);
		} catch (error) {
			if (isAccessError(error)) {
				setAccessDenied(true);
			} else {
				toast.error(t("antibot_load_failed"));
			}
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		void load();
	}, [load]);

	async function handleResolve(id: number) {
		try {
			await antiBotEscalationsApiService.resolve(id);
			toast.success(t("antibot_resolved"));
			await load();
		} catch {
			toast.error(t("antibot_resolve_failed"));
		}
	}

	async function handleRetry(id: number) {
		try {
			await antiBotEscalationsApiService.retry(id);
			toast.success(t("antibot_retry_enqueued"));
			await load();
		} catch {
			toast.error(t("antibot_retry_failed"));
		}
	}

	if (userLoading) {
		return (
			<div className="flex h-full items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	if (accessDenied) {
		return (
			<div className="flex h-full flex-col items-center justify-center gap-4 p-6">
				<h1 className="text-2xl font-semibold">{t("antibot_access_denied")}</h1>
				<p className="text-muted-foreground">{t("antibot_access_denied_desc")}</p>
			</div>
		);
	}

	return (
		<div className="container mx-auto max-w-6xl p-6">
			<div className="mb-6">
				<h1 className="font-serif text-2xl sm:text-3xl font-normal">{t("antibot_title")}</h1>
				<p className="text-xs sm:text-sm text-muted-foreground font-sans">
					{t("antibot_subtitle")}
				</p>
			</div>

			{loading ? (
				<div className="flex h-64 items-center justify-center">
					<Spinner size="lg" />
				</div>
			) : escalations.length === 0 ? (
				<Card>
					<CardContent className="flex h-40 items-center justify-center text-muted-foreground">
						{t("antibot_empty")}
					</CardContent>
				</Card>
			) : (
				<div className="space-y-4">
					{escalations.map((escalation) => (
						<Card key={escalation.id}>
							<CardHeader className="pb-3">
								<div className="flex items-start justify-between gap-4">
									<div>
										<CardTitle>
											{escalation.domain} — {escalation.capability}
										</CardTitle>
										<p className="text-sm text-muted-foreground">
											{t("antibot_block_type")}: {escalation.block_type} · {t("antibot_status")}:{" "}
											{escalation.status} ·{t("antibot_detections")}: {escalation.detection_count}
										</p>
									</div>
									<div className="flex items-center gap-2">
										<Button
											variant="outline"
											size="sm"
											onClick={() => handleResolve(escalation.id)}
											disabled={escalation.status === "resolved"}
										>
											{t("antibot_resolve")}
										</Button>
										<Button variant="outline" size="sm" onClick={() => handleRetry(escalation.id)}>
											{t("antibot_retry")}
										</Button>
									</div>
								</div>
							</CardHeader>
							<CardContent className="space-y-2 text-sm">
								<p className="text-muted-foreground">
									{t("antibot_run")}: {escalation.run_id} · {t("antibot_created")}:{" "}
									{new Date(escalation.created_at).toLocaleString()}
								</p>
								{escalation.screenshot_url && (
									<Image
										unoptimized
										src={`${BACKEND_URL}${escalation.screenshot_url}`}
										alt={t("antibot_screenshot_alt", { domain: escalation.domain })}
										width={800}
										height={400}
										className="mt-2 max-h-64 rounded border object-contain"
									/>
								)}
							</CardContent>
						</Card>
					))}
				</div>
			)}
		</div>
	);
}
