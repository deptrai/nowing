import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { ContactFormGridWithDetails } from "@/components/contact/contact-form";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("home");
	return {
		title: t("contact_meta_title"),
		description: t("contact_meta_description"),
		alternates: {
			canonical: "https://www.nowing.com/contact",
		},
	};
}

const page = () => {
	return (
		<div>
			<ContactFormGridWithDetails />
		</div>
	);
};

export default page;
