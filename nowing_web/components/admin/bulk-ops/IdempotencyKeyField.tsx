"use client";

import { Check, Copy, RefreshCw } from "lucide-react";
import React from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface IdempotencyKeyFieldProps {
	idempotencyKey: string;
	onRegenerate: () => void;
	disabled?: boolean;
}

export function IdempotencyKeyField({
	idempotencyKey,
	onRegenerate,
	disabled = false,
}: IdempotencyKeyFieldProps) {
	const [copied, setCopied] = React.useState(false);

	const handleCopy = async () => {
		try {
			await navigator.clipboard.writeText(idempotencyKey);
			setCopied(true);
			toast.success("Idempotency key copied to clipboard");
			setTimeout(() => setCopied(false), 2000);
		} catch {
			toast.error("Failed to copy key");
		}
	};

	return (
		<div className="space-y-1.5">
			<div className="flex items-center justify-between">
				<Label htmlFor="idempotency-key" className="text-xs font-medium text-muted-foreground">
					Idempotency Key (UUID v4)
				</Label>
				<span className="text-[11px] text-muted-foreground">Guards against duplicate runs</span>
			</div>
			<div className="flex items-center gap-2">
				<Input
					id="idempotency-key"
					value={idempotencyKey}
					readOnly
					disabled={disabled}
					className="font-mono text-xs h-9 bg-muted/30"
				/>
				<Button
					type="button"
					variant="outline"
					size="icon"
					onClick={handleCopy}
					disabled={disabled || !idempotencyKey}
					title="Copy key"
					className="h-9 w-9 shrink-0"
				>
					{copied ? (
						<Check className="h-3.5 w-3.5 text-green-500" />
					) : (
						<Copy className="h-3.5 w-3.5" />
					)}
				</Button>
				<Button
					type="button"
					variant="outline"
					size="sm"
					onClick={onRegenerate}
					disabled={disabled}
					className="h-9 gap-1.5 text-xs shrink-0"
				>
					<RefreshCw className="h-3.5 w-3.5" />
					Regenerate
				</Button>
			</div>
		</div>
	);
}
