"use client";

import { AlertCircle, AlertTriangle, EyeOff, Info } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { HealthAlertItem } from "@/lib/apis/admin-health-api.service";

interface AlertBannerProps {
	alerts: HealthAlertItem[];
	onAcknowledge: (alertId: number) => Promise<void>;
}

export default function AlertBanner({ alerts, onAcknowledge }: AlertBannerProps) {
	if (!alerts || alerts.length === 0) {
		return null;
	}

	const getSeverityVariant = (severity: string) => {
		switch (severity) {
			case "critical":
				return {
					variant: "destructive" as const,
					badgeVariant: "destructive" as const,
					icon: AlertCircle,
					label: "CRITICAL",
				};
			case "warning":
				return {
					variant: "default" as const,
					badgeVariant: "secondary" as const,
					icon: AlertTriangle,
					label: "WARNING",
				};
			default:
				return {
					variant: "default" as const,
					badgeVariant: "outline" as const,
					icon: Info,
					label: "INFO",
				};
		}
	};

	return (
		<div className="space-y-3" data-testid="health-alert-banner">
			{alerts.map((alert) => {
				const conf = getSeverityVariant(alert.severity);
				const Icon = conf.icon;

				return (
					<Alert
						key={alert.id}
						variant={conf.variant}
						className="border-l-4 border-l-red-500 bg-red-50/50 dark:bg-red-950/20"
					>
						<Icon className="h-4 w-4" />
						<div className="flex w-full items-center justify-between gap-4">
							<div className="space-y-1">
								<div className="flex items-center gap-2">
									<Badge variant={conf.badgeVariant} className="text-xs">
										{conf.label}
									</Badge>
									<AlertTitle className="font-semibold text-sm">{alert.service_id}</AlertTitle>
								</div>
								<AlertDescription className="text-sm">{alert.message}</AlertDescription>
							</div>

							<div className="flex items-center gap-2 shrink-0">
								<Button
									size="sm"
									variant="outline"
									className="text-xs h-8"
									onClick={() => onAcknowledge(alert.id)}
									data-testid={`acknowledge-alert-${alert.id}`}
								>
									<EyeOff className="h-3.5 w-3.5 mr-1" />
									Acknowledge (60m)
								</Button>
							</div>
						</div>
					</Alert>
				);
			})}
		</div>
	);
}
