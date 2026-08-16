"use client";

import { useEffect } from "react";
import { AnnouncementCard } from "@/components/announcements/AnnouncementCard";
import { AnnouncementsEmptyState } from "@/components/announcements/AnnouncementsEmptyState";
import { useAnnouncements } from "@/hooks/use-announcements";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AnnouncementsPage() {
	const { announcements, markAllRead } = useAnnouncements({ includeExpired: true });

	// Auto-mark all visible announcements as read when the page is opened
	useEffect(() => {
		markAllRead();
	}, [markAllRead]);

	return (
		<div className="min-h-screen relative pt-20">
			{/* Header */}
			<div className="border-b border-border/50">
				<div className="max-w-5xl mx-auto relative">
					<div className="p-6">
						<h1 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-normal tracking-tight text-neutral-900 dark:text-neutral-50">
							What&apos;s New
						</h1>
					</div>
				</div>
			</div>

			{/* Content */}
			<div className="max-w-3xl mx-auto px-6 lg:px-10 pt-8 pb-20">
				{announcements.length === 0 ? (
					<AnnouncementsEmptyState />
				) : (
					<div className="flex flex-col gap-4">
						{announcements.map((announcement) => (
							<AnnouncementCard key={announcement.id} announcement={announcement} />
						))}
					</div>
				)}
			</div>
		</div>
	);
}
