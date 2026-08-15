"use client";

import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { FooterNew } from "@/components/homepage/footer-new";
import { GlobalAnnouncement } from "@/components/homepage/global-announcement";
import { Navbar } from "@/components/homepage/navbar";
import { useReferralTracker } from "@/hooks/useReferralTracker";

function ReferralTracker() {
	useReferralTracker();
	return null;
}

export default function HomePageLayout({ children }: { children: React.ReactNode }) {
	const pathname = usePathname();
	const isAuthPage = pathname === "/login" || pathname === "/register";
	const isFreeModelChat = /^\/free\/[^/]+$/.test(pathname);

	if (isFreeModelChat) {
		return <>{children}</>;
	}

	return (
		<main className="min-h-screen bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white overflow-x-hidden">
			<Suspense fallback={null}>
				<ReferralTracker />
			</Suspense>
			<GlobalAnnouncement />
			<Navbar />
			{children}
			{!isAuthPage && <FooterNew />}
		</main>
	);
}
