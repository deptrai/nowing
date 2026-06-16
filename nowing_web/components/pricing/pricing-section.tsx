"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Pricing } from "@/components/pricing";
import { isAuthenticated, redirectToLogin, authenticatedFetch } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";

const PLAN_IDS = {
	pro_monthly: "pro_monthly",
	pro_yearly: "pro_yearly",
	max_monthly: "max_monthly",
	max_yearly: "max_yearly",
};

function PricingBasic() {
	const [isOnline, setIsOnline] = useState(true);
	const [isYearly, setIsYearly] = useState(false);
	const [isLoading, setIsLoading] = useState(false);
	const [isLoadingMax, setIsLoadingMax] = useState(false);

	useEffect(() => {
		setIsOnline(navigator.onLine);
		const handleOnline = () => setIsOnline(true);
		const handleOffline = () => setIsOnline(false);
		window.addEventListener("online", handleOnline);
		window.addEventListener("offline", handleOffline);
		return () => {
			window.removeEventListener("online", handleOnline);
			window.removeEventListener("offline", handleOffline);
		};
	}, []);

	const handleUpgradePro = async () => {
		if (!isOnline || isLoading) return;

		if (!isAuthenticated()) {
			redirectToLogin();
			return;
		}

		setIsLoading(true);
		try {
			const planId = isYearly ? PLAN_IDS.pro_yearly : PLAN_IDS.pro_monthly;
			const response = await authenticatedFetch(
				`${BACKEND_URL}/api/v1/stripe/create-subscription-checkout`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					body: JSON.stringify({ plan_id: planId }),
				}
			);

			if (!response.ok) {
				if (response.status === 503) {
					toast.error("Payment not configured on this server. Contact the administrator.");
				} else if (response.status === 409) {
					const errBody = await response.json().catch(() => ({}));
					toast.error(errBody?.detail ?? "You already have an active subscription or pending request.");
				} else {
					toast.error("Unable to start checkout. Please try again later.");
				}
				return;
			}

			const data = await response.json();

			if (data.admin_approval_mode) {
				toast.success("Subscription request submitted! An admin will approve it shortly.");
				return;
			}

			const checkoutUrl = data.checkout_url;
			if (typeof checkoutUrl === "string" && checkoutUrl.startsWith("https://")) {
				window.location.href = checkoutUrl;
			} else {
				toast.error("Invalid checkout response. Please try again.");
			}
		} catch (error) {
			toast.error("Something went wrong. Please check your connection and try again.");
		} finally {
			setIsLoading(false);
		}
	};

	const handleUpgradeMax = async () => {
		if (!isOnline || isLoadingMax) return;

		if (!isAuthenticated()) {
			redirectToLogin();
			return;
		}

		setIsLoadingMax(true);
		try {
			const planId = isYearly ? PLAN_IDS.max_yearly : PLAN_IDS.max_monthly;
			const response = await authenticatedFetch(
				`${BACKEND_URL}/api/v1/stripe/create-subscription-checkout`,
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ plan_id: planId }),
				}
			);

			if (!response.ok) {
				if (response.status === 503) {
					toast.error("Payment not configured on this server. Contact the administrator.");
				} else if (response.status === 409) {
					const errBody = await response.json().catch(() => ({}));
					toast.error(errBody?.detail ?? "You already have an active subscription or pending request.");
				} else {
					toast.error("Unable to start checkout. Please try again later.");
				}
				return;
			}

			const data = await response.json();

			if (data.admin_approval_mode) {
				toast.success("Subscription request submitted! An admin will approve it shortly.");
				return;
			}

			const checkoutUrl = data.checkout_url;
			if (typeof checkoutUrl === "string" && checkoutUrl.startsWith("https://")) {
				window.location.href = checkoutUrl;
			} else {
				toast.error("Invalid checkout response. Please try again.");
			}
		} catch {
			toast.error("Something went wrong. Please check your connection and try again.");
		} finally {
			setIsLoadingMax(false);
		}
	};

	// Pricing plans — static constant (loads offline)
	const demoPlans = [
		{
			name: "FREE",
			price: "0",
			yearlyPrice: "0",
			period: "month",
			billingText: "No credit card required",
			features: [
				"500 pages ETL / month",
				"50K LLM tokens / month",
				"50 LLM messages / day",
				"Standard models (GPT-4o mini, Haiku)",
				"Community support on Discord",
			],
			description: "Try Nowing free, forever",
			buttonText: "Get Started Free",
			href: "/login",
			isPopular: false,
		},
		{
			name: "PRO",
			price: "12",
			yearlyPrice: "8",
			period: "month",
			billingText: isYearly ? "billed annually ($96/yr, save $48)" : "billed monthly",
			features: [
				"Everything in Free",
				"5,000 pages ETL / month",
				"1M LLM tokens / month",
				"Unlimited LLM messages",
				"Premium models (GPT-4o, Claude Sonnet, Gemini)",
				"Priority support on Discord",
			],
			description: "For individuals and power users",
			buttonText: isLoading
				? "Redirecting…"
				: isOnline
					? "Upgrade to Pro"
					: "Offline — unavailable",
			href: "#",
			isPopular: true,
			onAction: handleUpgradePro,
			disabled: !isOnline || isLoading,
		},
		{
			name: "MAX",
			price: "100",
			yearlyPrice: "80",
			period: "month",
			billingText: isYearly ? "billed annually ($960/yr, save $240)" : "billed monthly",
			features: [
				"Everything in Pro",
				"20,000 pages ETL / month",
				"20M LLM tokens / month",
				"Unlimited LLM messages",
				"All models incl. GPT-4o, Claude Opus, Gemini Ultra",
				"Faster response priority",
				"Early access to new features",
				"Priority support",
			],
			description: "For heavy users who need maximum power",
			buttonText: isLoadingMax
				? "Redirecting…"
				: isOnline
					? "Upgrade to Max"
					: "Offline — unavailable",
			href: "#",
			isPopular: false,
			onAction: handleUpgradeMax,
			disabled: !isOnline || isLoadingMax,
		},
		{
			name: "ENTERPRISE",
			price: "Custom",
			yearlyPrice: "Custom",
			period: "",
			billingText: "Tailored to your team",
			features: [
				"Everything in Max",
				"Unlimited pages ETL",
				"Unlimited LLM tokens",
				"Unlimited LLM messages",
				"All models including latest releases",
				"On-prem or VPC deployment",
				"SSO, OIDC & SAML",
				"Audit logs & compliance",
				"Dedicated support & SLA",
			],
			description: "Custom setup for teams & organisations",
			buttonText: "Contact Sales",
			href: "mailto:rohan@nowing.com?subject=Enterprise%20Inquiry",
			isPopular: false,
		},
	];

	return (
		<Pricing
			plans={demoPlans}
			title="Nowing Pricing"
			description="Start free. Upgrade when you need more power."
			isYearly={isYearly}
			onToggleBilling={setIsYearly}
		/>
	);
}

export default PricingBasic;
