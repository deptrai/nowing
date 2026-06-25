import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import Image from "next/image";
export const baseOptions: BaseLayoutProps = {
	nav: {
		title: (
			<>
				<Image src="/icon-128.svg" alt="Nowing" width={24} height={24} className="dark:invert" />
				Nowing Docs
			</>
		),
	},
};
