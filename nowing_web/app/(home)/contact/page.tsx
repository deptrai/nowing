import type { Metadata } from "next";
import { ContactFormGridWithDetails } from "@/components/contact/contact-form";

export const metadata: Metadata = {
	title: "Contact | Nowing",
	description: "Get in touch with the Nowing team for enterprise AI search, knowledge management, or partnership inquiries.",
	alternates: {
		canonical: "https://nowing.com/contact",
	},
};

const page = () => {
	return (
		<div>
			<ContactFormGridWithDetails />
		</div>
	);
};

export default page;
