"use client";

import { useAtom } from "jotai";
import { useTranslations } from "next-intl";
import { showMessageTimestampsAtom } from "@/atoms/chat/show-timestamps.atom";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export function AppearanceContent() {
	const t = useTranslations("userSettings");
	const [showTimestamps, setShowTimestamps] = useAtom(showMessageTimestampsAtom);

	return (
		<div className="flex flex-col gap-4 md:gap-6">
			<section>
				<div className="pb-2 md:pb-3">
					<h2 className="text-base md:text-lg font-semibold">Chat</h2>
					<p className="text-xs md:text-sm text-muted-foreground">{t("appearance_lede")}</p>
				</div>
				<div className="flex flex-col gap-3">
					<div className="flex items-center justify-between rounded-lg bg-accent p-4">
						<div className="space-y-0.5">
							<Label
								htmlFor="show-timestamps-toggle"
								className="text-sm font-medium cursor-pointer"
							>
								{t("show_timestamps")}
							</Label>
							<p className="text-xs text-muted-foreground">{t("show_timestamps_desc")}</p>
						</div>
						<Switch
							id="show-timestamps-toggle"
							checked={showTimestamps}
							onCheckedChange={setShowTimestamps}
						/>
					</div>
				</div>
			</section>
		</div>
	);
}
