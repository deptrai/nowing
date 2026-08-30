"use client";

import { useAtom } from "jotai";
import { X } from "lucide-react";
import Image from "next/image";
import type { FC } from "react";
import { pendingUserImageDataUrlsAtom } from "@/atoms/chat/pending-user-images.atom";
import { Button } from "@/components/ui/button";

export const PendingScreenImageStrip: FC = () => {
	const [urls, setUrls] = useAtom(pendingUserImageDataUrlsAtom);
	if (urls.length === 0) return null;
	return (
		<div className="mx-3 mt-2 flex flex-wrap gap-2">
			{urls.map((url, index) => (
				<div
					key={url}
					className="group relative h-14 w-14 shrink-0 overflow-hidden rounded-md border border-border/50 bg-muted"
				>
					<Image
						src={url}
						alt="Pending screenshot preview"
						fill
						sizes="56px"
						className="object-cover"
						draggable={false}
						unoptimized
					/>
					<Button
						type="button"
						onClick={() => setUrls((prev) => prev.filter((_, i) => i !== index))}
						variant="ghost"
						size="icon"
						className="absolute right-0.5 top-0.5 size-5 rounded-full bg-background/90 text-muted-foreground shadow-sm transition-opacity hover:bg-background/90 hover:text-accent-foreground sm:opacity-0 sm:group-hover:opacity-100"
						aria-label="Remove screenshot"
					>
						<X className="size-3" aria-hidden="true" />
					</Button>
				</div>
			))}
		</div>
	);
};
