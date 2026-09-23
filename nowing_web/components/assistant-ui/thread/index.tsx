"use client";

import { AuiIf, ThreadPrimitive } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import type { FC } from "react";
import { dockOpenAtom } from "@/atoms/layout/dock.atom";
import { AssistantMessage } from "@/components/assistant-ui/assistant-message";
import { ChatViewport } from "@/components/assistant-ui/chat-viewport";
import { UserMessage } from "@/components/assistant-ui/user-message";
import { Composer } from "./Composer";
import { EditComposer } from "./EditComposer";
import { PremiumQuotaPinnedAlert } from "./PremiumQuotaPinnedAlert";
import { ThreadWelcome } from "./ThreadWelcome";
import type { ThreadProps } from "./types";

export const Thread: FC<ThreadProps> = ({ hasActiveThread = false, initialPrompt }) => {
	return <ThreadContent hasActiveThread={hasActiveThread} initialPrompt={initialPrompt} />;
};

const ThreadContent: FC<ThreadProps> = ({ hasActiveThread = false, initialPrompt }) => {
	const isDockOpen = useAtomValue(dockOpenAtom);
	// When Canvas/Dock is open, chat occupies a fixed left column, so 100% width is ideal.
	// When Canvas is closed, limit reading width to 48rem (768px) centered to avoid line stretching.
	const threadMaxWidth = hasActiveThread && isDockOpen ? "100%" : "48rem";

	return (
		<ThreadPrimitive.Root
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-main-panel"
			style={{
				["--thread-max-width" as string]: threadMaxWidth,
			}}
		>
			<ChatViewport
				hasActiveThread={hasActiveThread}
				footer={
					<>
						<PremiumQuotaPinnedAlert />
						<Composer initialPrompt={initialPrompt} hasActiveThread={hasActiveThread} />
					</>
				}
			>
				<AuiIf condition={({ thread }) => !hasActiveThread && thread.isEmpty}>
					<ThreadWelcome initialPrompt={initialPrompt} />
				</AuiIf>

				<ThreadPrimitive.Messages
					components={{
						UserMessage,
						EditComposer,
						AssistantMessage,
					}}
				/>
			</ChatViewport>
		</ThreadPrimitive.Root>
	);
};
