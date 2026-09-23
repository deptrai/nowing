import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("terms");
	return {
		title: t("meta_title"),
		description: t("meta_description"),
		alternates: {
			canonical: "https://www.nowing.com/terms",
		},
	};
}

// Rendered per-request so the NEXT_LOCALE cookie can switch the language.
export const dynamic = "force-dynamic";

const SECTIONS = Array.from({ length: 12 }, (_, i) => i + 1);

export default async function TermsOfService() {
	const t = await getTranslations("terms");
	return (
		<div className="container max-w-4xl mx-auto py-12 px-4">
			<h1 className="font-serif text-3xl sm:text-4xl font-normal mb-6">{t("title")}</h1>

			<div className="prose dark:prose-invert max-w-none">
				<p className="text-lg mb-6">
					{t("last_updated", { date: new Date().toLocaleDateString() })}
				</p>

				{SECTIONS.map((n) => {
					const paras = [1, 2, 3];
					return (
						<section key={n} className="mb-8">
							<h2 className="text-2xl font-semibold mb-4">{t(`s${n}_title`)}</h2>
							{paras.map((p) => {
								const key = `s${n}_p${p}`;
								const upper = t.has(`${key}_upper`);
								if (!t.has(key)) return null;
								return (
									<p key={key} className={upper ? "mt-4 uppercase font-bold" : "mt-4 first:mt-0"}>
										{t(key)}
									</p>
								);
							})}
							{n === 12 && (
								<p className="mt-2">
									<strong>Email:</strong> admin@nowing.com
								</p>
							)}
						</section>
					);
				})}
			</div>
		</div>
	);
}
