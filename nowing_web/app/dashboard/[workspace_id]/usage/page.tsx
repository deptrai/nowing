import type { Metadata } from "next";
import { UsageContent } from "@/components/usage/usage-content";

export const metadata: Metadata = {
	title: "Usage",
};

export default function UsagePage() {
	return (
		<div className="mx-auto w-full max-w-5xl py-6 md:py-8">
			<UsageContent />
		</div>
	);
}
