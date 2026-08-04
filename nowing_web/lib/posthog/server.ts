import { PostHog } from "posthog-node";

let posthogInstance: PostHog | null = null;

const noOpPostHog = {
	captureException: () => Promise.resolve(),
	capture: () => Promise.resolve(),
} as unknown as PostHog;

export default function PostHogClient() {
	if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) {
		return noOpPostHog;
	}

	if (!posthogInstance) {
		posthogInstance = new PostHog(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
			host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
			flushAt: 1,
			flushInterval: 0,
		});
	}

	return posthogInstance;
}
