import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("common");
	return {
		title: t("not_found_meta_title"),
		description: t("not_found_meta_description"),
	};
}

export default async function NotFound() {
	const t = await getTranslations("common");
	return (
		<div className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
			<h1 className="text-8xl font-bold tracking-tight text-neutral-900 dark:text-neutral-100">
				404
			</h1>
			<p className="mt-4 text-xl text-neutral-600 dark:text-neutral-400">
				{t("not_found_heading")}
			</p>
			<p className="mt-2 text-base text-neutral-500 dark:text-neutral-500">{t("not_found_desc")}</p>
			<div className="mt-10 flex flex-col items-center gap-4 sm:flex-row">
				<Link
					href="/"
					className="rounded-lg bg-black px-6 py-3 text-sm font-medium text-white transition hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200"
				>
					{t("not_found_go_home")}
				</Link>
				<Link
					href="/docs"
					className="rounded-lg border border-neutral-200 px-6 py-3 text-sm font-medium text-neutral-700 transition hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
				>
					{t("not_found_browse_docs")}
				</Link>
				<Link
					href="/blog"
					className="rounded-lg border border-neutral-200 px-6 py-3 text-sm font-medium text-neutral-700 transition hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
				>
					{t("not_found_read_blog")}
				</Link>
			</div>
			<nav className="mt-16 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-neutral-500 dark:text-neutral-400">
				<Link href="/pricing" className="hover:text-neutral-900 dark:hover:text-neutral-200">
					{t("not_found_pricing")}
				</Link>
				<Link href="/contact" className="hover:text-neutral-900 dark:hover:text-neutral-200">
					{t("not_found_contact")}
				</Link>
				<Link href="/changelog" className="hover:text-neutral-900 dark:hover:text-neutral-200">
					{t("not_found_changelog")}
				</Link>
			</nav>
		</div>
	);
}
