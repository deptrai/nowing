"use client";

import { useTranslations } from "next-intl";
import { Component, type ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

export * from "./plan";
export * from "./schema";

// ============================================================================
// Error Boundary
// ============================================================================

interface PlanErrorBoundaryProps {
	children: ReactNode;
	fallback?: ReactNode;
}

interface PlanErrorBoundaryState {
	hasError: boolean;
	error?: Error;
}

export class PlanErrorBoundary extends Component<PlanErrorBoundaryProps, PlanErrorBoundaryState> {
	constructor(props: PlanErrorBoundaryProps) {
		super(props);
		this.state = { hasError: false };
	}

	static getDerivedStateFromError(error: Error): PlanErrorBoundaryState {
		return { hasError: true, error };
	}

	render() {
		if (this.state.hasError) {
			if (this.props.fallback) {
				return this.props.fallback;
			}

			return (
				<Card className="w-full max-w-xl border-destructive/50">
					<CardContent className="pt-6">
						<div className="flex items-center gap-2 text-destructive">
							<PlanErrorText />
						</div>
					</CardContent>
				</Card>
			);
		}

		return this.props.children;
	}
}

function PlanErrorText() {
	const t = useTranslations("toolUi");
	return <span className="text-sm">{t("tu_failed_to_render_plan")}</span>;
}
