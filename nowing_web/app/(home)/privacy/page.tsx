import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("privacy");
	return {
		title: t("meta_title"),
		description: t("meta_description"),
		alternates: {
			canonical: "https://www.nowing.com/privacy",
		},
	};
}

// Rendered per-request so the NEXT_LOCALE cookie can switch the language.
export const dynamic = "force-dynamic";

const LAST_UPDATED = "May 21, 2026";

// Sections that contain a bullet list; each bullet i is stored as
// s{n}_b{i} (plain) or split into s{n}_b{i}_h (bold lead) + s{n}_b{i}_t (rest).
const LIST_SECTIONS = new Set([2, 3, 4, 5, 8, 9, 10]);
const LIST_COUNT: Record<number, number> = { 2: 11, 3: 8, 4: 4, 5: 5, 8: 6, 9: 7, 10: 5 };
// Paragraph counts per section (excluding intro line rendered separately when a list exists).
const PARA_COUNT: Record<number, number> = {
	1: 2,
	4: 2,
	5: 2,
	6: 2,
	7: 1,
	8: 2,
	9: 2,
	10: 2,
	11: 1,
	12: 1,
	13: 1,
	2: 0,
	3: 0,
};

export default async function PrivacyPolicy() {
	const t = await getTranslations("privacy");
	const rich = (key: string): ReactNode =>
		t.rich(key, {
			b: (c) => <strong>{c}</strong>,
			freeLink: (c) => <Link href="/free">{c}</Link>,
			adsSettings: (c) => <a href="https://www.google.com/settings/ads">{c}</a>,
			aboutAds: (c) => <a href="https://www.aboutads.info/choices/">{c}</a>,
			onlineChoices: (c) => <a href="https://www.youronlinechoices.com/">{c}</a>,
			googleInfo: (c) => <a href="https://policies.google.com/technologies/partner-sites">{c}</a>,
			email: (c) => <a href="mailto:admin@nowing.com">{c}</a>,
			website: (c) => <a href="https://www.nowing.com">{c}</a>,
		});

	return (
		<div className="container max-w-4xl mx-auto py-12 px-4">
			<h1 className="font-serif text-3xl sm:text-4xl font-normal mb-6">{t("title")}</h1>

			<div className="prose dark:prose-invert max-w-none">
				<p className="text-lg mb-6">{t("last_updated", { date: LAST_UPDATED })}</p>

				{Array.from({ length: 13 }, (_, i) => i + 1).map((n) => (
					<section key={n} className="mb-8">
						<h2 className="text-2xl font-semibold mb-4">{t(`s${n}_title`)}</h2>
						{Array.from({ length: PARA_COUNT[n] ?? 0 }, (_, p) => p + 1).map((p) => (
							<p key={p} className={p > 1 ? "mt-4" : undefined}>
								{rich(`s${n}_p${p}`)}
							</p>
						))}
						{LIST_SECTIONS.has(n) && (
							<ul className="list-disc pl-6 my-4 space-y-2">
								{Array.from({ length: LIST_COUNT[n] }, (_, i) => i + 1).map((i) => (
									<li key={i}>{rich(`s${n}_b${i}`)}</li>
								))}
							</ul>
						)}
						{n === 13 && (
							<p className="mt-2">
								<strong>Email:</strong> <a href="mailto:admin@nowing.com">admin@nowing.com</a>
							</p>
						)}
					</section>
				))}
			</div>
		</div>
	);
}
