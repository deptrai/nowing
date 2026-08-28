"use client";

import type React from "react";
import type { Lead } from "@/contracts/types/leads.types";
import { cn } from "@/lib/utils";
import { ContactChannelPill } from "./ContactChannelPill";
import { PhoneUnlockPill } from "./PhoneUnlockPill";

export interface ContactChannelsProps {
	lead: Lead;
	workspaceId: number | string;
	className?: string;
	onPhoneChange?: (leadId: string, phone: string | null, unlocked: boolean) => void;
	onChannelChange?: (
		leadId: string,
		channel: string,
		value: string | null,
		unlocked: boolean
	) => void;
}

export const ContactChannels: React.FC<ContactChannelsProps> = ({
	lead,
	workspaceId,
	className,
	onPhoneChange,
	onChannelChange,
}) => {
	const { email, external_chat_ids } = lead;

	return (
		<div className={cn("flex flex-wrap items-center gap-2", className)}>
			<PhoneUnlockPill
				lead={lead}
				workspaceId={workspaceId}
				onPhoneChange={onPhoneChange}
				showIcon
			/>

			{email && (
				<ContactChannelPill
					lead={lead}
					workspaceId={workspaceId}
					channel="email"
					value={email}
					onChange={onChannelChange}
				/>
			)}

			{external_chat_ids &&
				Object.entries(external_chat_ids).map(([channel, value]) =>
					value ? (
						<ContactChannelPill
							key={channel}
							lead={lead}
							workspaceId={workspaceId}
							channel={channel}
							value={value}
							onChange={onChannelChange}
						/>
					) : null
				)}
		</div>
	);
};
