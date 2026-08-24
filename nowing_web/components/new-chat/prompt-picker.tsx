"use client";

import { useAtomValue } from "jotai";
import { Globe, Plus, WandSparkles } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import {
	forwardRef,
	useCallback,
	useDeferredValue,
	useEffect,
	useImperativeHandle,
	useMemo,
	useRef,
	useState,
} from "react";

import { promptsAtom } from "@/atoms/prompts/prompts-query.atoms";
import {
	ComposerSuggestionGroup,
	ComposerSuggestionGroupHeading,
	ComposerSuggestionItem,
	ComposerSuggestionList,
	ComposerSuggestionMessage,
	ComposerSuggestionSeparator,
	ComposerSuggestionSkeleton,
} from "@/components/new-chat/composer-suggestion-popup";
import { getWorkspaceIdParam } from "@/lib/route-params";

export interface PromptPickerRef {
	selectHighlighted: () => void;
	moveUp: () => void;
	moveDown: () => void;
}

export interface PromptPickerAction {
	name: string;
	prompt: string;
	mode: "transform" | "explore";
	isWebBuilder?: boolean;
}

interface PromptPickerProps {
	onSelect: (action: PromptPickerAction) => void;
	onDone: () => void;
	externalSearch?: string;
}

interface BuiltinPromptItem {
	id: string;
	name: string;
	description: string;
	prompt: string;
	mode: "transform" | "explore";
	isWebBuilder: boolean;
}

const BUILTIN_TEMPLATES: BuiltinPromptItem[] = [
	{
		id: "web-landing-page",
		name: "/web landing page",
		description: "High-converting SaaS / product landing page",
		prompt:
			"Build a modern high-converting landing page for a SaaS product with hero section, feature cards, testimonial carousel, pricing comparison, and email CTA.",
		mode: "explore",
		isWebBuilder: true,
	},
	{
		id: "web-pricing",
		name: "/web pricing",
		description: "3-tier pricing page with billing toggle & FAQ",
		prompt:
			"Create a modern 3-tier pricing page with monthly/yearly billing toggle, feature comparison table, and FAQ accordion section.",
		mode: "explore",
		isWebBuilder: true,
	},
	{
		id: "web-lead-capture",
		name: "/web lead capture",
		description: "Lead capture & opt-in page with social proof",
		prompt:
			"Create an engaging lead capture page with an email opt-in form, value proposition highlights, benefit bullet points, and social proof badges.",
		mode: "explore",
		isWebBuilder: true,
	},
	{
		id: "web-waitlist",
		name: "/web waitlist",
		description: "Viral coming-soon waitlist page with countdown",
		prompt:
			"Build an exciting viral waitlist coming-soon page with early access email signup, countdown timer, and referral perk highlights.",
		mode: "explore",
		isWebBuilder: true,
	},
	{
		id: "web-report",
		name: "/web report",
		description: "Interactive marketing report & whitepaper page",
		prompt:
			"Generate a clean interactive marketing report and whitepaper showcase page with key metric callouts, interactive charts summary, and download CTA.",
		mode: "explore",
		isWebBuilder: true,
	},
];

export const PromptPicker = forwardRef<PromptPickerRef, PromptPickerProps>(function PromptPicker(
	{ onSelect, onDone, externalSearch = "" },
	ref
) {
	const router = useRouter();
	const params = useParams();
	const { data: prompts, isLoading, isError } = useAtomValue(promptsAtom);
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const shouldScrollRef = useRef(false);
	const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

	// Defer the search value so filtering is non-urgent and the input stays responsive
	const deferredSearch = useDeferredValue(externalSearch);

	const normalizedSearch = useMemo(() => {
		let q = deferredSearch.trim().toLowerCase();
		if (q.startsWith("/")) q = q.slice(1);
		return q;
	}, [deferredSearch]);

	const filteredBuiltins = useMemo(() => {
		if (!normalizedSearch) return BUILTIN_TEMPLATES;
		return BUILTIN_TEMPLATES.filter(
			(item) =>
				item.name.toLowerCase().includes(normalizedSearch) ||
				item.description.toLowerCase().includes(normalizedSearch) ||
				item.prompt.toLowerCase().includes(normalizedSearch)
		);
	}, [normalizedSearch]);

	const filteredSaved = useMemo(() => {
		const list = prompts ?? [];
		if (!normalizedSearch) return list;
		return list.filter((a) => a.name.toLowerCase().includes(normalizedSearch));
	}, [prompts, normalizedSearch]);

	// Flat list of selectable items for keyboard indexing
	const flatItems = useMemo(() => {
		const items: {
			id: string | number;
			name: string;
			prompt: string;
			mode: "transform" | "explore";
			isWebBuilder?: boolean;
		}[] = [];

		for (const b of filteredBuiltins) {
			items.push({
				id: b.id,
				name: b.name,
				prompt: b.prompt,
				mode: b.mode,
				isWebBuilder: true,
			});
		}

		for (const s of filteredSaved) {
			items.push({
				id: s.id,
				name: s.name,
				prompt: s.prompt,
				mode: s.mode,
				isWebBuilder: false,
			});
		}

		return items;
	}, [filteredBuiltins, filteredSaved]);

	// Reset highlight when the deferred (filtered) search changes
	const prevSearchRef = useRef(deferredSearch);
	if (prevSearchRef.current !== deferredSearch) {
		prevSearchRef.current = deferredSearch;
		if (highlightedIndex !== 0) {
			setHighlightedIndex(0);
		}
	}

	const createPromptIndex = flatItems.length;
	const totalItems = flatItems.length + 1;
	const workspaceId = getWorkspaceIdParam(params);

	const handleSelect = useCallback(
		(index: number) => {
			if (index === createPromptIndex) {
				onDone();
				if (workspaceId) {
					router.push(`/dashboard/${workspaceId}/user-settings/prompts`);
				}
				return;
			}
			const action = flatItems[index];
			if (!action) return;
			onSelect({
				name: action.name,
				prompt: action.prompt,
				mode: action.mode,
				isWebBuilder: action.isWebBuilder,
			});
		},
		[flatItems, onSelect, createPromptIndex, onDone, router, workspaceId]
	);

	useEffect(() => {
		if (!shouldScrollRef.current) return;
		shouldScrollRef.current = false;

		const rafId = requestAnimationFrame(() => {
			const item = itemRefs.current.get(highlightedIndex);
			const container = scrollContainerRef.current;
			if (item && container) {
				const itemRect = item.getBoundingClientRect();
				const containerRect = container.getBoundingClientRect();
				if (itemRect.top < containerRect.top || itemRect.bottom > containerRect.bottom) {
					item.scrollIntoView({ block: "nearest" });
				}
			}
		});

		return () => cancelAnimationFrame(rafId);
	}, [highlightedIndex]);

	useImperativeHandle(
		ref,
		() => ({
			selectHighlighted: () => handleSelect(highlightedIndex),
			moveUp: () => {
				shouldScrollRef.current = true;
				setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : totalItems - 1));
			},
			moveDown: () => {
				shouldScrollRef.current = true;
				setHighlightedIndex((prev) => (prev < totalItems - 1 ? prev + 1 : 0));
			},
		}),
		[totalItems, highlightedIndex, handleSelect]
	);

	const hasNoResults = flatItems.length === 0;

	return (
		<ComposerSuggestionList ref={scrollContainerRef}>
			{isLoading ? (
				<ComposerSuggestionSkeleton rows={8} mobileRows={8} />
			) : isError ? (
				<ComposerSuggestionMessage variant="destructive">
					Failed to load prompts
				</ComposerSuggestionMessage>
			) : hasNoResults ? (
				<ComposerSuggestionMessage>No matching prompts</ComposerSuggestionMessage>
			) : (
				<>
					{/* Web Builder Templates Group */}
					{filteredBuiltins.length > 0 && (
						<ComposerSuggestionGroup>
							<ComposerSuggestionGroupHeading>Web Builder Templates</ComposerSuggestionGroupHeading>
							{filteredBuiltins.map((builtin, i) => {
								const flatIdx = i;
								return (
									<ComposerSuggestionItem
										key={builtin.id}
										ref={(el) => {
											if (el) itemRefs.current.set(flatIdx, el);
											else itemRefs.current.delete(flatIdx);
										}}
										icon={<Globe className="size-3.5 text-teal-600 dark:text-teal-400" />}
										selected={flatIdx === highlightedIndex}
										onClick={() => handleSelect(flatIdx)}
										onMouseEnter={() => setHighlightedIndex(flatIdx)}
									>
										<div className="flex flex-col min-w-0 flex-1">
											<span className="truncate text-xs font-medium">{builtin.name}</span>
											<span className="truncate text-[10px] text-muted-foreground">
												{builtin.description}
											</span>
										</div>
									</ComposerSuggestionItem>
								);
							})}
						</ComposerSuggestionGroup>
					)}

					{filteredBuiltins.length > 0 && filteredSaved.length > 0 && (
						<ComposerSuggestionSeparator />
					)}

					{/* Saved Prompts Group */}
					{filteredSaved.length > 0 && (
						<ComposerSuggestionGroup>
							<ComposerSuggestionGroupHeading>Saved Prompts</ComposerSuggestionGroupHeading>
							{filteredSaved.map((action, i) => {
								const flatIdx = filteredBuiltins.length + i;
								return (
									<ComposerSuggestionItem
										key={action.id}
										ref={(el) => {
											if (el) itemRefs.current.set(flatIdx, el);
											else itemRefs.current.delete(flatIdx);
										}}
										icon={<WandSparkles className="size-3.5" />}
										selected={flatIdx === highlightedIndex}
										onClick={() => handleSelect(flatIdx)}
										onMouseEnter={() => setHighlightedIndex(flatIdx)}
									>
										<span className="flex-1 truncate text-xs">{action.name}</span>
									</ComposerSuggestionItem>
								);
							})}
						</ComposerSuggestionGroup>
					)}

					<ComposerSuggestionSeparator />
					<ComposerSuggestionItem
						ref={(el) => {
							if (el) itemRefs.current.set(createPromptIndex, el);
							else itemRefs.current.delete(createPromptIndex);
						}}
						icon={<Plus className="size-3.5" />}
						muted
						selected={highlightedIndex === createPromptIndex}
						onClick={() => handleSelect(createPromptIndex)}
						onMouseEnter={() => setHighlightedIndex(createPromptIndex)}
					>
						<span>Create prompt</span>
					</ComposerSuggestionItem>
				</>
			)}
		</ComposerSuggestionList>
	);
});
