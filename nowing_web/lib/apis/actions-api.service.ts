import { actionCatalog } from "@/contracts/types/action.types";
import { baseApiService } from "./base-api.service";

const BASE = "/api/v1/automations/actions";

class ActionsApiService {
	listActions = async () => {
		return baseApiService.get(BASE, actionCatalog);
	};
}

export const actionsApiService = new ActionsApiService();
