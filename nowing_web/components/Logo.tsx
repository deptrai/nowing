import Link from "next/link";
import { OrigamiLogo } from "@/components/origami/OrigamiLogo";
import { cn } from "@/lib/utils";

export const Logo = ({
	className,
	disableLink = false,
	showText = false,
}: {
	className?: string;
	disableLink?: boolean;
	priority?: boolean;
	showText?: boolean;
}) => {
	const content = (
		<OrigamiLogo
			size={32}
			showText={showText}
			className={cn("select-none", className)}
		/>
	);

	if (disableLink) {
		return content;
	}

	return (
		<Link href="/" className="select-none inline-flex items-center">
			{content}
		</Link>
	);
};
