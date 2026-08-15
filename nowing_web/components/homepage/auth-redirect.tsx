"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/hooks/use-session";

export function AuthRedirect() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const session = useSession();

	const isPreview = searchParams.get("preview") === "1";

	useEffect(() => {
		if (!isPreview && session.status === "authenticated") {
			router.replace("/dashboard");
		}
	}, [router, session.status, isPreview]);

	return null;
}
