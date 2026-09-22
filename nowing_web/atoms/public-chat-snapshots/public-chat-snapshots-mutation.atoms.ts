import { atomWithMutation } from "jotai-tanstack-query";
import { translateToast } from "@/lib/i18n-toast";
import { toast } from "sonner";
import type {
	PublicChatSnapshotCreateRequest,
	PublicChatSnapshotCreateResponse,
	PublicChatSnapshotDeleteRequest,
} from "@/contracts/types/chat-threads.types";
import { chatThreadsApiService } from "@/lib/apis/chat-threads-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const createPublicChatSnapshotMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (request: PublicChatSnapshotCreateRequest) => {
		return chatThreadsApiService.createPublicChatSnapshot(request);
	},
	onSuccess: (response: PublicChatSnapshotCreateResponse) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.publicChatSnapshots.all,
		});

		const publicUrl = `${window.location.origin}/public/${response.share_token}`;
		navigator.clipboard.writeText(publicUrl);
		if (response.is_new) {
			toast.success(translateToast("toast.public_link_created_copied"), {
				description: translateToast("toast.public_link_created_desc"),
			});
		} else {
			toast.success(translateToast("toast.public_link_copied"), {
				description: translateToast("toast.public_link_copied_desc"),
			});
		}
	},
	onError: (error: Error) => {
		console.error("Failed to create snapshot:", error);
		toast.error(translateToast("toast.public_link_create_failed"));
	},
}));

export const deletePublicChatSnapshotMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (request: PublicChatSnapshotDeleteRequest) => {
		return chatThreadsApiService.deletePublicChatSnapshot(request);
	},
	onSuccess: () => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.publicChatSnapshots.all,
		});
		toast.success(translateToast("toast.public_link_deleted"));
	},
	onError: (error: Error) => {
		console.error("Failed to delete public chat:", error);
		toast.error(translateToast("toast.public_link_delete_failed"));
	},
}));
