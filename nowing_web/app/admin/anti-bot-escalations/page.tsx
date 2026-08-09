"use client";

import { useAtom } from "jotai";
import Image from "next/image";
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
				toast.error("Failed to load anti-bot escalations");
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
			toast.success("Escalation resolved");
			await load();
		} catch {
			toast.error("Failed to resolve escalation");
		}
	}

	async function handleRetry(id: number) {
		try {
			await antiBotEscalationsApiService.retry(id);
			toast.success("Retry enqueued");
			await load();
		} catch {
			toast.error("Failed to enqueue retry");
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
				<h1 className="text-2xl font-semibold">Access denied</h1>
				<p className="text-muted-foreground">
					You must be a workspace Owner, Editor, or superuser to view this page.
				</p>
			</div>
		);
	}

	return (
		<div className="container mx-auto max-w-6xl p-6">
			<div className="mb-6">
				<h1 className="text-2xl font-semibold">Anti-bot escalations</h1>
				<p className="text-sm text-muted-foreground">
					Review CAPTCHA and anti-bot blocks captured from scraper runs.
				</p>
			</div>

			{loading ? (
				<div className="flex h-64 items-center justify-center">
					<Spinner size="lg" />
				</div>
			) : escalations.length === 0 ? (
				<Card>
					<CardContent className="flex h-40 items-center justify-center text-muted-foreground">
						No anti-bot escalations found.
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
											Block type: {escalation.block_type} · Status: {escalation.status} ·
											Detections: {escalation.detection_count}
										</p>
									</div>
									<div className="flex items-center gap-2">
										<Button
											variant="outline"
											size="sm"
											onClick={() => handleResolve(escalation.id)}
											disabled={escalation.status === "resolved"}
										>
											Resolve
										</Button>
										<Button variant="outline" size="sm" onClick={() => handleRetry(escalation.id)}>
											Retry
										</Button>
									</div>
								</div>
							</CardHeader>
							<CardContent className="space-y-2 text-sm">
								<p className="text-muted-foreground">
									Run: {escalation.run_id} · Created:{" "}
									{new Date(escalation.created_at).toLocaleString()}
								</p>
								{escalation.screenshot_url && (
									<Image
										unoptimized
										src={`${BACKEND_URL}${escalation.screenshot_url}`}
										alt={`Screenshot for ${escalation.domain}`}
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
