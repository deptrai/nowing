"use client";

import { useAtom } from "jotai";
import { Bell } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { setTargetCommentIdAtom } from "@/atoms/chat/current-thread.atom";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
	isAlertRunCompleteMetadata,
	isCommentReplyMetadata,
	isInsufficientCreditsMetadata,
	isNewMentionMetadata,
} from "@/contracts/types/inbox.types";
import type { InboxItem } from "@/hooks/use-inbox";
import { useIsMobile } from "@/hooks/use-mobile";
import {
	groupInboxNotifications,
	type InboxNotificationGroup,
} from "@/lib/alerts/group-inbox-notifications";
import { cn } from "@/lib/utils";

export interface NotificationsDataSource {
	items: InboxItem[];
	unreadCount: number;
	totalCount?: number;
	loading: boolean;
	loadingMore?: boolean;
	hasMore?: boolean;
	loadMore?: () => void;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
}

export interface NotificationsDropdownData {
	totalUnreadCount: number;
	comments: NotificationsDataSource;
	status: NotificationsDataSource;
}

interface NotificationsDropdownProps {
	notifications: NotificationsDropdownData;
	onCloseMobileSidebar?: () => void;
}

type NotificationFilter = "all" | "mentions" | "unread";

function formatNotificationCount(count: number): string {
	if (count <= 999) {
		return count.toString();
	}
	const thousands = Math.floor(count / 1000);
	return `${thousands}k+`;
}

function formatTime(dateString: string): string {
	try {
		const date = new Date(dateString);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / (1000 * 60));
		const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
		const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

		if (diffMins < 1) return "now";
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffHours < 24) return `${diffHours}h ago`;
		if (diffDays < 7) return `${diffDays}d ago`;
		return `${Math.floor(diffDays / 7)}w ago`;
	} catch {
		return "now";
	}
}

function isCommentNotification(item: InboxItem): boolean {
	return item.type === "new_mention" || item.type === "comment_reply";
}

export function NotificationsDropdown({
	notifications,
	onCloseMobileSidebar,
}: NotificationsDropdownProps) {
	const router = useRouter();
	const isMobile = useIsMobile();
	const [, setTargetCommentId] = useAtom(setTargetCommentIdAtom);
	const [open, setOpen] = useState(false);
	const [activeFilter, setActiveFilter] = useState<NotificationFilter>("all");
	const [markingAsReadId, setMarkingAsReadId] = useState<number | null>(null);
	const [markingAllAsRead, setMarkingAllAsRead] = useState(false);
	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const loadMoreTriggerRef = useRef<HTMLDivElement>(null);

	const unreadLabel = formatNotificationCount(notifications.totalUnreadCount);
	const allCount =
		(notifications.comments.totalCount ?? 0) + (notifications.status.totalCount ?? 0);
	const mentionsCount = notifications.comments.totalCount ?? notifications.comments.items.length;
	const visibleUnreadCount =
		activeFilter === "mentions"
			? notifications.comments.unreadCount
			: notifications.totalUnreadCount;
	const isLoading =
		activeFilter === "mentions"
			? notifications.comments.loading
			: notifications.comments.loading || notifications.status.loading;
	const isLoadingMore =
		activeFilter === "mentions"
			? !!notifications.comments.loadingMore
			: !!notifications.comments.loadingMore || !!notifications.status.loadingMore;
	const hasMore =
		activeFilter === "mentions"
			? !!notifications.comments.hasMore
			: !!notifications.comments.hasMore || !!notifications.status.hasMore;
	const { groupedItems } = useMemo(() => {
		const sourceItems =
			activeFilter === "mentions"
				? notifications.comments.items
				: [...notifications.comments.items, ...notifications.status.items];

		const filtered = sourceItems.filter((item) => activeFilter !== "unread" || !item.read);
		const sorted = filtered.toSorted(
			(a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
		);

		const { groups, others } = groupInboxNotifications(sorted);
		const groupedItems: (InboxItem | InboxNotificationGroup)[] = [...groups, ...others].toSorted(
			(a, b) => {
				const aTime =
					"alert_rule_id" in a
						? new Date(a.latest_created_at).getTime()
						: new Date(a.created_at).getTime();
				const bTime =
					"alert_rule_id" in b
						? new Date(b.latest_created_at).getTime()
						: new Date(b.created_at).getTime();
				return bTime - aTime;
			}
		);

		return { groupedItems };
	}, [activeFilter, notifications.comments.items, notifications.status.items]);

	const loadMoreForActiveFilter = useCallback(() => {
		if (isLoadingMore) return;

		if (activeFilter === "mentions") {
			if (notifications.comments.hasMore) {
				notifications.comments.loadMore?.();
			}
			return;
		}

		if (notifications.comments.hasMore) {
			notifications.comments.loadMore?.();
		}
		if (notifications.status.hasMore) {
			notifications.status.loadMore?.();
		}
	}, [activeFilter, isLoadingMore, notifications.comments, notifications.status]);

	useEffect(() => {
		if (!open || isLoading || isLoadingMore || !hasMore) return;
		const root = scrollContainerRef.current;
		const target = loadMoreTriggerRef.current;
		if (!root || !target) return;

		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) {
					loadMoreForActiveFilter();
				}
			},
			{
				root,
				rootMargin: "120px",
				threshold: 0,
			}
		);

		observer.observe(target);
		return () => observer.disconnect();
	}, [hasMore, isLoading, isLoadingMore, loadMoreForActiveFilter, open]);

	const markItemAsRead = useCallback(
		async (item: InboxItem) => {
			if (item.read) return;
			setMarkingAsReadId(item.id);
			try {
				await (isCommentNotification(item)
					? notifications.comments.markAsRead(item.id)
					: notifications.status.markAsRead(item.id));
			} finally {
				setMarkingAsReadId(null);
			}
		},
		[notifications.comments, notifications.status]
	);

	const handleItemClick = useCallback(
		async (item: InboxItem | InboxNotificationGroup) => {
			if ("alert_rule_id" in item) {
				const latest = item.items[0];
				const snapshotId = latest?.metadata?.snapshot_id;
				if (latest?.workspace_id) {
					setOpen(false);
					onCloseMobileSidebar?.();
					const query = snapshotId ? `?snapshot=${snapshotId}` : "";
					router.push(
						`/dashboard/${latest.workspace_id}/research/saved-searches/${item.alert_rule_id}${query}`
					);
				} else {
					console.warn("Alert group missing workspace_id, skipping navigation", item);
				}
				return;
			}

			await markItemAsRead(item);

			if (item.type === "new_mention" && isNewMentionMetadata(item.metadata)) {
				const threadId = item.metadata.thread_id;
				const commentId = item.metadata.comment_id;
				if (item.workspace_id && threadId) {
					if (commentId) setTargetCommentId(commentId);
					setOpen(false);
					onCloseMobileSidebar?.();
					router.push(
						commentId
							? `/dashboard/${item.workspace_id}/new-chat/${threadId}?commentId=${commentId}`
							: `/dashboard/${item.workspace_id}/new-chat/${threadId}`
					);
				}
				return;
			}

			if (item.type === "comment_reply" && isCommentReplyMetadata(item.metadata)) {
				const threadId = item.metadata.thread_id;
				const replyId = item.metadata.reply_id;
				if (item.workspace_id && threadId) {
					if (replyId) setTargetCommentId(replyId);
					setOpen(false);
					onCloseMobileSidebar?.();
					router.push(
						replyId
							? `/dashboard/${item.workspace_id}/new-chat/${threadId}?commentId=${replyId}`
							: `/dashboard/${item.workspace_id}/new-chat/${threadId}`
					);
				}
				return;
			}

			if (item.type === "insufficient_credits" && isInsufficientCreditsMetadata(item.metadata)) {
				if (item.metadata.action_url) {
					setOpen(false);
					onCloseMobileSidebar?.();
					router.push(item.metadata.action_url);
				}
			}

			if (item.type === "alert_run_complete" && isAlertRunCompleteMetadata(item.metadata)) {
				const alertRuleId = item.metadata.alert_rule_id;
				const snapshotId = item.metadata.snapshot_id;
				if (item.workspace_id && alertRuleId) {
					setOpen(false);
					onCloseMobileSidebar?.();
					router.push(
						`/dashboard/${item.workspace_id}/research/saved-searches/${alertRuleId}?snapshot=${snapshotId}`
					);
				}
			}
		},
		[markItemAsRead, onCloseMobileSidebar, router, setTargetCommentId]
	);

	const handleMarkAllAsRead = useCallback(async () => {
		if (visibleUnreadCount === 0 || markingAllAsRead) return;
		setMarkingAllAsRead(true);
		try {
			if (activeFilter === "mentions") {
				await notifications.comments.markAllAsRead();
			} else {
				await Promise.all([
					notifications.comments.markAllAsRead(),
					notifications.status.markAllAsRead(),
				]);
			}
		} finally {
			setMarkingAllAsRead(false);
		}
	}, [activeFilter, markingAllAsRead, notifications, visibleUnreadCount]);

	const emptyStateCopy =
		activeFilter === "mentions"
			? {
					title: "No mentions",
					description: "Mentions and replies will appear here.",
				}
			: activeFilter === "unread"
				? {
						title: "No unread notifications",
						description: "New mentions and status updates will appear here.",
					}
				: {
						title: "No notifications",
						description: "Mentions, replies, and status updates will appear here.",
					};

	const tabs: { value: NotificationFilter; label: string; count: number }[] = [
		{ value: "all", label: "All", count: allCount },
		{ value: "mentions", label: "Mentions", count: mentionsCount },
		{ value: "unread", label: "Unread", count: notifications.totalUnreadCount },
	];

	const triggerButton = (
		<Button
			type="button"
			variant="ghost"
			size="icon"
			aria-label="Notifications"
			className={cn(
				"relative h-10 w-10 rounded-lg text-muted-foreground hover:bg-accent hover:text-accent-foreground",
				open && "bg-accent text-accent-foreground"
			)}
		>
			<Bell className="h-4 w-4" />
			{notifications.totalUnreadCount > 0 ? (
				<span className="absolute right-1 top-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground">
					{unreadLabel}
				</span>
			) : null}
		</Button>
	);

	const panelContent = (
		<>
			<div className="flex shrink-0 items-center justify-between gap-3 border-b px-3.5 py-2.5">
				<div className="min-w-0">
					<h2 className="text-xs font-semibold tracking-tight text-foreground">Notifications</h2>
				</div>
				<Button
					type="button"
					variant="ghost"
					size="sm"
					onClick={handleMarkAllAsRead}
					disabled={visibleUnreadCount === 0 || markingAllAsRead}
					className="h-6 shrink-0 gap-1 px-1.5 text-[10.5px] text-muted-foreground hover:text-accent-foreground"
				>
					{markingAllAsRead ? <Spinner size="xs" /> : null}
					Mark all read
				</Button>
			</div>

			<div className="relative flex shrink-0 items-end gap-3 px-3.5 after:absolute after:inset-x-0 after:bottom-0 after:z-0 after:h-px after:bg-muted-foreground/20 after:content-['']">
				{tabs.map((tab) => {
					const isActive = activeFilter === tab.value;
					return (
						<button
							key={tab.value}
							type="button"
							aria-pressed={isActive}
							onClick={() => setActiveFilter(tab.value)}
							className={cn(
								"relative z-10 flex h-8 items-center gap-1.5 border-b-2 border-transparent px-0 text-xs font-medium text-muted-foreground transition-colors",
								"hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
								isActive && "border-primary text-primary font-semibold"
							)}
						>
							<span>{tab.label}</span>
							<span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-muted px-1 text-[9.5px] font-semibold text-muted-foreground font-mono">
								{formatNotificationCount(tab.count)}
							</span>
						</button>
					);
				})}
			</div>

			<div ref={scrollContainerRef} className="min-h-0 flex-1 overflow-y-auto p-1.5">
				{isLoading ? (
					<div className="space-y-1">
						{[82, 64, 74].map((width) => (
							<div key={width} className="flex h-14 items-center rounded-md px-2 py-1.5">
								<div className="min-w-0 flex-1 space-y-1.5">
									<Skeleton className="h-2.5 rounded" style={{ width: `${width}%` }} />
									<Skeleton className="h-2 w-1/2 rounded" />
								</div>
							</div>
						))}
					</div>
				) : groupedItems.length > 0 ? (
					<div className="space-y-0.5">
						{groupedItems.map((item) => {
							const isGroup = "alert_rule_id" in item;
							const isMarkingAsRead = isGroup ? false : markingAsReadId === item.id;
							const key = isGroup ? `group-${item.alert_rule_id}` : item.id;
							const title = isGroup ? item.rule_name : item.title;
							const message = isGroup
								? `+${item.match_count} new match${item.match_count === 1 ? "" : "es"}`
								: item.message;
							const createdAt = isGroup ? item.latest_created_at : item.created_at;
							const unread = isGroup ? item.unread : !item.read;
							return (
								<Button
									key={key}
									type="button"
									variant="ghost"
									disabled={isMarkingAsRead}
									onClick={() => handleItemClick(item)}
									className={cn(
										"group h-auto w-full justify-start rounded-md px-2 py-1.5 text-left",
										"hover:bg-accent hover:text-accent-foreground",
										unread && "bg-accent/40"
									)}
									style={{ contentVisibility: "auto", containIntrinsicSize: "0 56px" }}
								>
									<div className="min-w-0 flex-1">
										<div className="flex min-w-0 items-start gap-1.5">
											<p
												className={cn(
													"line-clamp-1 flex-1 text-xs font-medium",
													unread && "font-semibold text-foreground"
												)}
											>
												{title}
											</p>
											{unread ? (
												<span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
											) : null}
										</div>
										<p className="mt-0.5 line-clamp-2 text-[11px] font-normal text-muted-foreground group-hover:text-accent-foreground/80 leading-snug">
											{message}
										</p>
										<p className="mt-0.5 text-[10px] font-normal text-muted-foreground/70 font-mono">
											{formatTime(createdAt)}
										</p>
									</div>
									{isMarkingAsRead ? <Spinner size="xs" className="shrink-0" /> : null}
								</Button>
							);
						})}
						{hasMore ? (
							<div
								ref={loadMoreTriggerRef}
								className="flex min-h-8 items-center justify-center py-1.5"
							>
								{isLoadingMore ? <Spinner size="xs" /> : null}
							</div>
						) : null}
					</div>
				) : (
					<div className="flex min-h-full flex-col items-center justify-center px-4 py-8 text-center">
						<p className="text-xs font-semibold text-foreground">{emptyStateCopy.title}</p>
						<p className="mt-0.5 text-[11px] text-muted-foreground leading-relaxed">
							{emptyStateCopy.description}
						</p>
					</div>
				)}
			</div>
		</>
	);

	if (isMobile) {
		return (
			<Drawer open={open} onOpenChange={setOpen} shouldScaleBackground={false}>
				<DrawerTrigger asChild>{triggerButton}</DrawerTrigger>
				<DrawerContent
					className="z-80 h-[78vh] max-h-[90vh] overflow-hidden rounded-t-2xl border bg-popover text-popover-foreground"
					overlayClassName="z-80"
				>
					<DrawerHandle className="mt-3 h-1.5 w-10" />
					<DrawerTitle className="sr-only">Notifications</DrawerTitle>
					<div className="flex min-h-0 flex-1 select-none flex-col">{panelContent}</div>
				</DrawerContent>
			</Drawer>
		);
	}

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<Tooltip>
				<TooltipTrigger asChild>
					<PopoverTrigger asChild>{triggerButton}</PopoverTrigger>
				</TooltipTrigger>
				<TooltipContent side="right" sideOffset={8}>
					Notifications
				</TooltipContent>
			</Tooltip>
			<PopoverContent
				side="right"
				align="end"
				sideOffset={10}
				className="z-80 flex h-[min(420px,calc(100vh-2rem))] w-[360px] select-none flex-col overflow-hidden rounded-xl border bg-popover p-0 text-popover-foreground shadow-lg"
			>
				{panelContent}
			</PopoverContent>
		</Popover>
	);
}
