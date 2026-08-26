"use client";

import { useAtomValue } from "jotai";
import { Globe, Mic, Plus, Presentation, WandSparkles } from "lucide-react";
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
	chatMode?: "web_builder" | "presentation_studio" | "meeting_minutes";
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
	chatMode?: "web_builder" | "presentation_studio" | "meeting_minutes";
}

const BUILTIN_TEMPLATES: BuiltinPromptItem[] = [
	{
		id: "web-landing-page",
		name: "/web landing page",
		description: "High-converting SaaS / product landing page",
		prompt:
			"Build a modern high-converting landing page for a SaaS product with hero section, feature cards, testimonial carousel, pricing comparison, and email CTA.",
		mode: "explore",
		chatMode: "web_builder",
	},
	{
		id: "web-pricing",
		name: "/web pricing",
		description: "3-tier pricing page with billing toggle & FAQ",
		prompt:
			"Create a modern 3-tier pricing page with monthly/yearly billing toggle, feature comparison table, and FAQ accordion section.",
		mode: "explore",
		chatMode: "web_builder",
	},
	{
		id: "web-lead-capture",
		name: "/web lead capture",
		description: "Lead capture & opt-in page with social proof",
		prompt:
			"Create an engaging lead capture page with an email opt-in form, value proposition highlights, benefit bullet points, and social proof badges.",
		mode: "explore",
		chatMode: "web_builder",
	},
	{
		id: "web-waitlist",
		name: "/web waitlist",
		description: "Viral coming-soon waitlist page with countdown",
		prompt:
			"Build an exciting viral waitlist coming-soon page with early access email signup, countdown timer, and referral perk highlights.",
		mode: "explore",
		chatMode: "web_builder",
	},
	{
		id: "web-report",
		name: "/web report",
		description: "Interactive marketing report & whitepaper page",
		prompt:
			"Generate a clean interactive marketing report and whitepaper showcase page with key metric callouts, interactive charts summary, and download CTA.",
		mode: "explore",
		chatMode: "web_builder",
	},
	{
		id: "slides-pptx",
		name: "/slides pptx",
		description: "Pitch deck as a PowerPoint PPTX file",
		prompt:
			"Create a 10-slide pitch deck as a PowerPoint PPTX file. Call generate_presentation with output_format=pptx. Cover problem, solution, market size, business model, traction, team, financials, and ask.",
		mode: "explore",
		chatMode: "presentation_studio",
	},
	{
		id: "slides-marp",
		name: "/slides marp",
		description: "Marp Markdown slide deck",
		prompt:
			"Create Marp Markdown slides. Call generate_presentation with output_format=marp. Include YAML front-matter (theme, paginate), a title slide, content slides, and speaker notes.",
		mode: "explore",
		chatMode: "presentation_studio",
	},
	{
		id: "meeting-minutes",
		name: "/meeting",
		description: "Summarize a meeting from an audio URL",
		prompt: "Paste the meeting recording URL here",
		mode: "explore",
		chatMode: "meeting_minutes",
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
	const filteredWebBuiltins = useMemo(
		() => filteredBuiltins.filter((b) => b.chatMode === "web_builder"),
		[filteredBuiltins]
	);
	const filteredPresentationBuiltins = useMemo(
		() => filteredBuiltins.filter((b) => b.chatMode === "presentation_studio"),
		[filteredBuiltins]
	);
	const filteredMeetingMinutesBuiltins = useMemo(
		() => filteredBuiltins.filter((b) => b.chatMode === "meeting_minutes"),
		[filteredBuiltins]
	);

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
			chatMode?: "web_builder" | "presentation_studio" | "meeting_minutes";
		}[] = [];

		for (const b of filteredPresentationBuiltins) {
			items.push({
				id: b.id,
				name: b.name,
				prompt: b.prompt,
				mode: b.mode,
				chatMode: b.chatMode,
			});
		}

		for (const b of filteredWebBuiltins) {
			items.push({
				id: b.id,
				name: b.name,
				prompt: b.prompt,
				mode: b.mode,
				chatMode: b.chatMode,
			});
		}

		for (const b of filteredMeetingMinutesBuiltins) {
			items.push({
				id: b.id,
				name: b.name,
				prompt: b.prompt,
				mode: b.mode,
				chatMode: b.chatMode,
			});
		}

		for (const s of filteredSaved) {
			items.push({
				id: s.id,
				name: s.name,
				prompt: s.prompt,
				mode: s.mode,
			});
		}

		return items;
	}, [
		filteredPresentationBuiltins,
		filteredWebBuiltins,
		filteredMeetingMinutesBuiltins,
		filteredSaved,
	]);

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
				chatMode: action.chatMode,
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

	const savedStartIdx =
		filteredPresentationBuiltins.length +
		filteredWebBuiltins.length +
		filteredMeetingMinutesBuiltins.length;

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
					{/* Presentation Studio Templates Group */}
					{filteredPresentationBuiltins.length > 0 && (
						<ComposerSuggestionGroup>
							<ComposerSuggestionGroupHeading>
								Presentation Studio Templates
							</ComposerSuggestionGroupHeading>
							{filteredPresentationBuiltins.map((builtin, i) => {
								const flatIdx = i;
								return (
									<ComposerSuggestionItem
										key={builtin.id}
										ref={(el) => {
											if (el) itemRefs.current.set(flatIdx, el);
											else itemRefs.current.delete(flatIdx);
										}}
										icon={
											<Presentation className="size-3.5 text-purple-600 dark:text-purple-400" />
										}
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

					{filteredPresentationBuiltins.length > 0 && filteredWebBuiltins.length > 0 && (
						<ComposerSuggestionSeparator />
					)}

					{/* Web Builder Templates Group */}
					{filteredWebBuiltins.length > 0 && (
						<ComposerSuggestionGroup>
							<ComposerSuggestionGroupHeading>Web Builder Templates</ComposerSuggestionGroupHeading>
							{filteredWebBuiltins.map((builtin, i) => {
								const flatIdx = filteredPresentationBuiltins.length + i;
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

					{(filteredPresentationBuiltins.length > 0 ||
						filteredWebBuiltins.length > 0 ||
						filteredMeetingMinutesBuiltins.length > 0) &&
						filteredSaved.length > 0 && <ComposerSuggestionSeparator />}

					{/* Meeting Minutes Templates Group */}
					{filteredMeetingMinutesBuiltins.length > 0 && (
						<ComposerSuggestionGroup>
							<ComposerSuggestionGroupHeading>Meeting Minutes</ComposerSuggestionGroupHeading>
							{filteredMeetingMinutesBuiltins.map((builtin, i) => {
								const flatIdx =
									filteredPresentationBuiltins.length + filteredWebBuiltins.length + i;
								return (
									<ComposerSuggestionItem
										key={builtin.id}
										ref={(el) => {
											if (el) itemRefs.current.set(flatIdx, el);
											else itemRefs.current.delete(flatIdx);
										}}
										icon={<Mic className="size-3.5 text-emerald-600 dark:text-emerald-400" />}
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

					{/* Saved Prompts Group */}
					{filteredSaved.length > 0 && (
						<ComposerSuggestionGroup>
							<ComposerSuggestionGroupHeading>Saved Prompts</ComposerSuggestionGroupHeading>
							{filteredSaved.map((action, i) => {
								const flatIdx = savedStartIdx + i;
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
