"use client";

import { ComposerPrimitive, MessagePrimitive } from "@assistant-ui/react";
import type { FC } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export const EditComposer: FC = () => {
	const tChat = useTranslations("chat");
	const tCommon = useTranslations("common");
	return (
		<MessagePrimitive.Root className="aui-edit-composer-wrapper mx-auto flex w-full max-w-(--thread-max-width) flex-col px-2 py-3">
			<ComposerPrimitive.Root className="aui-edit-composer-root ml-auto flex w-full max-w-[85%] flex-col rounded-2xl bg-muted">
				<ComposerPrimitive.Input
					className="aui-edit-composer-input min-h-14 w-full resize-none bg-transparent p-4 text-foreground text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
					autoFocus
					aria-label={tChat("edit_message")}
					role="textbox"
				/>
				<div className="aui-edit-composer-footer mx-3 mb-3 flex items-center gap-2 self-end">
					<ComposerPrimitive.Cancel asChild>
						<Button variant="ghost" size="sm">
							{tCommon("cancel")}
						</Button>
					</ComposerPrimitive.Cancel>
					<ComposerPrimitive.Send asChild>
						<Button size="sm">{tCommon("update")}</Button>
					</ComposerPrimitive.Send>
				</div>
			</ComposerPrimitive.Root>
		</MessagePrimitive.Root>
	);
};
