"use client";

import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { hasProEntitlement } from "@/lib/entitlements";

/**
 * Hook to check if the current user has an active Pro subscription.
 *
 * Single source of truth: delegates entirely to `hasProEntitlement`, which
 * also handles superuser bypass and the "cancelled-but-still-paid-through-
 * period-end" grace window.
 *
 * @returns { isPro: boolean, isLoading: boolean }
 */
export function useSubscriptionGate() {
	const { data: user, isPending, isError } = useAtomValue(currentUserAtom);

	const isPro = useMemo(() => {
		if (isError || !user) return false;
		return hasProEntitlement(user);
	}, [user, isError]);

	return {
		isPro,
		isLoading: isPending,
	};
}
