"use client";

import { useAtomValue } from "jotai";
import { BookOpen, Play } from "lucide-react";
import { useState } from "react";
import { instantiatePlaybookMutationAtom } from "@/atoms/playbooks/playbooks-mutation.atoms";
import { playbooksListAtom } from "@/atoms/playbooks/playbooks-query.atoms";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import type { PlaybookSummary } from "@/contracts/types/playbook.types";

interface PlaybooksContentProps {
	workspaceId: number;
}

export function PlaybooksContent({ workspaceId }: PlaybooksContentProps) {
	const { data, isLoading, error } = useAtomValue(playbooksListAtom);
	const { mutateAsync: instantiate, isPending: instantiating } = useAtomValue(
		instantiatePlaybookMutationAtom
	);
	const [inputsJson, setInputsJson] = useState<Record<number, string>>({});

	const playbooks = data?.items ?? [];

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

	async function handleInstantiate(playbook: PlaybookSummary) {
		let inputs: Record<string, unknown> = {};
		const raw = inputsJson[playbook.id];
		if (raw?.trim()) {
			try {
				inputs = JSON.parse(raw);
			} catch {
				// Let the backend reject invalid JSON with a clear message.
			}
		}
		await instantiate({
			playbookId: playbook.id,
			request: { workspace_id: workspaceId, inputs },
		});
	}

	return (
		<div className="space-y-4">
			<div className="flex items-baseline gap-3">
				<h1 className="text-xl md:text-2xl font-semibold text-foreground">Playbooks</h1>
				<span className="text-sm text-muted-foreground">
					{playbooks.length} {playbooks.length === 1 ? "playbook" : "playbooks"}
				</span>
			</div>

			<div className="grid grid-cols-1 gap-4">
				{playbooks.map((playbook) => (
					<Card key={playbook.id} className="rounded-md border-accent bg-accent/20">
						<CardHeader className="pb-3">
							<CardTitle className="text-sm font-semibold">{playbook.name}</CardTitle>
							{playbook.description && (
								<p className="text-xs text-muted-foreground">{playbook.description}</p>
							)}
						</CardHeader>
						<CardContent className="space-y-3">
							<div className="space-y-1">
								<label
									htmlFor={`inputs-${playbook.id}`}
									className="text-xs font-medium text-muted-foreground"
								>
									Inputs (JSON)
								</label>
								<Input
									id={`inputs-${playbook.id}`}
									placeholder='{"query": "Hanoi apartments"}'
									value={inputsJson[playbook.id] ?? ""}
									onChange={(e) =>
										setInputsJson((prev) => ({
											...prev,
											[playbook.id]: e.target.value,
										}))
									}
								/>
							</div>
							<Button
								size="sm"
								disabled={instantiating}
								onClick={() => handleInstantiate(playbook)}
							>
								<Play className="mr-1 h-4 w-4" />
								Instantiate
							</Button>
						</CardContent>
					</Card>
				))}
			</div>
		</div>
	);
}
