"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { BookOpen, Play } from "lucide-react";
import { useMemo, useState } from "react";
import { playbooksListAtom } from "@/atoms/playbooks/playbooks-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import type { PlaybookSummary } from "@/contracts/types/playbook.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { PlaybookInstantiateDialog } from "./playbook-instantiate-dialog";

interface PlaybooksContentProps {
	workspaceId: number;
}

export function PlaybooksContent({ workspaceId }: PlaybooksContentProps) {
	const { data, isLoading, error } = useAtomValue(playbooksListAtom);
	const [selectedPlaybook, setSelectedPlaybook] = useState<PlaybookSummary | null>(null);

	const { data: workspace } = useQuery({
		queryKey: [...cacheKeys.workspaces.detail(String(workspaceId))],
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});

	const playbooks = data?.items ?? [];
	const workspaceVertical = workspace?.vertical ?? "general";

	const grouped = useMemo(() => {
		const map = new Map<string, PlaybookSummary[]>();
		for (const playbook of playbooks) {
			const groupKey =
				playbook.verticals.find((v) => v === workspaceVertical) ??
				playbook.verticals[0] ??
				"general";
			const list = map.get(groupKey) ?? [];
			list.push(playbook);
			map.set(groupKey, list);
		}
		return Array.from(map.entries()).sort(([a], [b]) => {
			if (a === workspaceVertical) return -1;
			if (b === workspaceVertical) return 1;
			return a.localeCompare(b);
		});
	}, [playbooks, workspaceVertical]);

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner />
			</div>
		);
	}

	if (error) {
		return (
			<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-12 text-center">
				<h2 className="text-base font-semibold text-foreground">Could not load playbooks</h2>
				<p className="mt-1 text-sm text-muted-foreground">{error.message}</p>
			</div>
		);
	}

	if (playbooks.length === 0) {
		return (
			<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-12 text-center">
				<BookOpen className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden />
				<h2 className="mt-3 text-base font-semibold text-foreground">No playbooks yet</h2>
				<p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
					Save an automation as a playbook to reuse it with different inputs.
				</p>
			</div>
		);
	}

	return (
		<div className="space-y-6">
			<div className="flex items-baseline gap-3">
				<h1 className="text-xl md:text-2xl font-semibold text-foreground">Playbooks</h1>
				<span className="text-sm text-muted-foreground">
					{playbooks.length} {playbooks.length === 1 ? "playbook" : "playbooks"}
				</span>
				<Badge variant="secondary" className="ml-auto capitalize">
					{workspaceVertical.replace(/_/g, " ")}
				</Badge>
			</div>

			{grouped.map(([vertical, items]) => (
				<section key={vertical} className="space-y-3">
					<h2 className="text-sm font-medium text-muted-foreground capitalize">
						{vertical.replace(/_/g, " ")}
					</h2>
					<div className="grid grid-cols-1 gap-4">
						{items.map((playbook) => (
							<Card key={playbook.id} className="rounded-md border-accent bg-accent/20">
								<CardHeader className="pb-3">
									<div className="flex items-start justify-between gap-3">
										<CardTitle className="text-sm font-semibold">{playbook.name}</CardTitle>
										<div className="flex flex-wrap gap-1">
											{playbook.verticals.map((v) => (
												<Badge key={v} variant="outline" className="text-xs capitalize">
													{v.replace(/_/g, " ")}
												</Badge>
											))}
										</div>
									</div>
									{playbook.description && (
										<p className="text-xs text-muted-foreground">{playbook.description}</p>
									)}
								</CardHeader>
								<CardContent>
									<Button size="sm" onClick={() => setSelectedPlaybook(playbook)}>
										<Play className="mr-1 h-4 w-4" />
										Instantiate
									</Button>
								</CardContent>
							</Card>
						))}
					</div>
				</section>
			))}

			{selectedPlaybook && (
				<PlaybookInstantiateDialog
					playbook={selectedPlaybook}
					workspaceId={workspaceId}
					open={!!selectedPlaybook}
					onOpenChange={() => setSelectedPlaybook(null)}
				/>
			)}
		</div>
	);
}
