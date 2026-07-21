# SurfSense Backend - API Contracts

**Ngày tạo:** 2026-07-21 16:59:34

## Tổng quan

Backend FastAPI exposes hơn 300 endpoints qua các module route. Các route chính được mount tại `/api/v1` (CRUD router) cùng các route auth tại `/auth`, `/users`, health check `/health`, `/ready`, `/verify-token`.

## Cấu trúc router

- `app/routes/__init__.py` xây dựng `crud_router` và đăng ký tất cả module route.
- `app/app.py` tạo `FastAPI` instance, đăng ký middleware, auth routers, `crud_router` với prefix `/api/v1`.
- Các module nhỏ: `app/automations/api.py`, `app/file_storage/api.py`, `app/notifications/api.py`, `app/podcasts/api/routes.py`, `app/gateway/*`.

## Danh sách endpoints theo nhóm

### `app/file_storage/api.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/documents/{document_id}/files` | `read_document_files` | Return metadata for every stored file of a document (gates the UI). |
| GET | `/documents/{document_id}/download-original` | `download_original_document_file` | Stream the document's original uploaded file. |

### `app/notifications/api/api.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/unread-counts-batch` | `get_unread_counts_batch` | Unread counts for every category in a single query. |
| GET | `/source-types` | `get_notification_source_types` | Distinct connector/document source types for the Status tab filter. |
| GET | `/unread-count` | `get_unread_count` | Total and recent (within sync window) unread counts for the user. |
| GET | `` | `list_notifications` | Paginated inbox fallback for items outside the Zero sync window. |
| PATCH | `/{notification_id}/read` | `mark_notification_as_read` | Mark one of the user's notifications read; Zero syncs the change. |
| PATCH | `/read-all` | `mark_all_notifications_as_read` | Mark all of the user's notifications read; Zero syncs the changes. |

### `app/podcasts/api/routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/podcasts` | `list_podcasts` |  |
| GET | `/podcasts/voices` | `list_voices` | Voices the active TTS provider offers, optionally filtered by language. |
| GET | `/podcasts/languages` | `list_languages` | Languages the active TTS provider can offer the brief editor. |
| GET | `/podcasts/voices/{voice_id}/preview` | `preview_voice` | A short audio sample of a voice, so users pick by sound. |
| POST | `/podcasts` | `create_podcast` |  |
| GET | `/podcasts/{podcast_id}` | `get_podcast` |  |
| PATCH | `/podcasts/{podcast_id}/spec` | `update_spec` |  |
| POST | `/podcasts/{podcast_id}/brief/approve` | `approve_brief` | Approve the brief and start drafting the transcript. |
| POST | `/podcasts/{podcast_id}/transcript/regenerate` | `regenerate_transcript` | Reopen the brief gate for a fresh take; drafting waits for re-approval. |
| POST | `/podcasts/{podcast_id}/regenerate/revert` | `revert_regeneration` | Back out of a regeneration and return to the finished episode. |
| POST | `/podcasts/{podcast_id}/cancel` | `cancel_podcast` |  |
| DELETE | `/podcasts/{podcast_id}` | `delete_podcast` |  |
| GET | `/podcasts/{podcast_id}/stream` | `stream_podcast` |  |

### `app/routes/agent_action_log_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/threads/{thread_id}/actions` | `list_thread_actions` | List agent actions for a thread, newest first. |

### `app/routes/agent_flags_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/agent/flags` | `get_agent_flags` |  |

### `app/routes/agent_permissions_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/workspaces/{workspace_id}/agent/permissions/rules` | `list_rules` |  |
| POST | `/workspaces/{workspace_id}/agent/permissions/rules` | `create_rule` |  |
| PATCH | `/workspaces/{workspace_id}/agent/permissions/rules/{rule_id}` | `update_rule` |  |
| DELETE | `/workspaces/{workspace_id}/agent/permissions/rules/{rule_id}` | `delete_rule` |  |

### `app/routes/agent_revert_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/threads/{thread_id}/revert/{action_id}` | `revert_agent_action` |  |
| POST | `/threads/{thread_id}/revert-turn/{chat_turn_id}` | `revert_agent_turn` | Revert every reversible action emitted during ``chat_turn_id``. |

### `app/routes/airtable_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/airtable/connector/add` | `connect_airtable` |  |
| GET | `/auth/airtable/connector/callback` | `airtable_callback` |  |

### `app/routes/anonymous_chat_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/models` | `list_anonymous_models` | Return all models enabled for anonymous access. |
| GET | `/models/{slug}` | `get_anonymous_model` | Return a single model by its SEO slug. |
| GET | `/quota` | `get_anonymous_quota` | Return current token usage for the anonymous session. |
| POST | `/stream` | `stream_anonymous_chat` | Stream a chat response for an anonymous user with quota enforcement. |
| POST | `/upload` | `upload_anonymous_document` | Upload a single document for anonymous chat (1-doc limit per session). |
| GET | `/document` | `get_anonymous_document` | Get metadata of the uploaded document for the anonymous session. |

### `app/routes/auth_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/refresh` | `refresh_access_token` |  |
| POST | `/revoke` | `revoke_token` |  |
| POST | `/logout-all` | `logout_all_devices` |  |
| GET | `/session` | `get_session` |  |
| POST | `/desktop/login` | `desktop_password_login` |  |
| POST | `/desktop/session` | `create_desktop_session` |  |

### `app/routes/chat_comments_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/messages/comments/batch` | `batch_list_comments` | Batch-fetch comments for multiple messages in one request. |
| GET | `/messages/{message_id}/comments` | `list_comments` | List all comments for a message with their replies. |
| POST | `/messages/{message_id}/comments` | `add_comment` | Create a top-level comment on an AI response. |
| POST | `/comments/{comment_id}/replies` | `add_reply` | Reply to an existing comment. |
| PUT | `/comments/{comment_id}` | `edit_comment` | Update a comment's content (author only). |
| DELETE | `/comments/{comment_id}` | `remove_comment` | Delete a comment (author or user with COMMENTS_DELETE permission). |
| GET | `/mentions` | `list_mentions` | List mentions for the current user. |

### `app/routes/circleback_webhook_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/webhooks/circleback/{workspace_id}` | `receive_circleback_webhook` |  |
| GET | `/webhooks/circleback/{workspace_id}/info` | `get_circleback_webhook_info` |  |

### `app/routes/clickup_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/clickup/connector/add` | `connect_clickup` |  |
| GET | `/auth/clickup/connector/callback` | `clickup_callback` |  |

### `app/routes/composio_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/composio/toolkits` | `list_composio_toolkits` |  |
| GET | `/auth/composio/connector/add` | `initiate_composio_auth` |  |
| GET | `/auth/composio/connector/callback` | `composio_callback` |  |
| GET | `/auth/composio/connector/reauth` | `reauth_composio_connector` |  |
| GET | `/auth/composio/connector/reauth/callback` | `composio_reauth_callback` |  |
| GET | `/connectors/{connector_id}/composio-drive/folders` | `list_composio_drive_folders` |  |

### `app/routes/confluence_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/confluence/connector/add` | `connect_confluence` |  |
| GET | `/auth/confluence/connector/callback` | `confluence_callback` |  |
| GET | `/auth/confluence/connector/reauth` | `reauth_confluence` | Initiate Confluence re-authentication to upgrade OAuth scopes. |

### `app/routes/discord_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/discord/connector/add` | `connect_discord` |  |
| GET | `/auth/discord/connector/callback` | `discord_callback` |  |
| GET | `/discord/connector/{connector_id}/channels` | `get_discord_channels` |  |

### `app/routes/documents_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/documents` | `create_documents` |  |
| POST | `/documents/fileupload` | `create_documents_file_upload` |  |
| GET | `/documents` | `read_documents` |  |
| GET | `/documents/search` | `search_documents` |  |
| POST | `/documents/search-semantic` | `search_documents_semantic` | Hybrid semantic + keyword search over a workspace's knowledge base. |
| GET | `/documents/search/titles` | `search_document_titles` |  |
| GET | `/documents/by-virtual-path` | `get_document_by_virtual_path` | Resolve a knowledge-base document by its agent-facing virtual path. |
| GET | `/documents/status` | `get_documents_status` |  |
| GET | `/documents/type-counts` | `get_document_type_counts` |  |
| GET | `/documents/by-chunk/{chunk_id}` | `get_document_by_chunk_id` |  |
| GET | `/documents/watched-folders` | `get_watched_folders` | Return root folders that are marked as watched (metadata->>'watched' = 'true'). |
| GET | `/documents/{document_id}/chunks` | `get_document_chunks_paginated` |  |
| GET | `/documents/{document_id}` | `read_document` |  |
| PUT | `/documents/{document_id}` | `update_document` |  |
| DELETE | `/documents/{document_id}` | `delete_document` |  |
| GET | `/documents/{document_id}/versions` | `list_document_versions` |  |
| GET | `/documents/{document_id}/versions/{version_number}` | `get_document_version` |  |
| POST | `/documents/{document_id}/versions/{version_number}/restore` | `restore_document_version` |  |
| POST | `/documents/folder-mtime-check` | `folder_mtime_check` | Pre-upload optimization: check which files need uploading based on mtime. |
| POST | `/documents/folder-upload` | `folder_upload` |  |
| POST | `/documents/folder-unlink` | `folder_unlink` | Handle file deletion events from the desktop watcher. |
| POST | `/documents/folder-sync-finalize` | `folder_sync_finalize` | Finalize a full folder scan by deleting orphaned documents. |

### `app/routes/dropbox_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/dropbox/connector/add` | `connect_dropbox` | Initiate Dropbox OAuth flow. |
| GET | `/auth/dropbox/connector/reauth` | `reauth_dropbox` | Re-authenticate an existing Dropbox connector. |
| GET | `/auth/dropbox/connector/callback` | `dropbox_callback` | Handle Dropbox OAuth callback. |
| GET | `/connectors/{connector_id}/dropbox/folders` | `list_dropbox_folders` | List folders and files in user's Dropbox. |

### `app/routes/editor_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/workspaces/{workspace_id}/documents/{document_id}/editor-content` | `get_editor_content` |  |
| GET | `/workspaces/{workspace_id}/documents/{document_id}/download-markdown` | `download_document_markdown` |  |
| POST | `/workspaces/{workspace_id}/documents/{document_id}/save` | `save_document` |  |
| GET | `/workspaces/{workspace_id}/documents/{document_id}/export` | `export_document` | Export a document in the requested format (reuses the report export pipeline). |

### `app/routes/export_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/workspaces/{workspace_id}/export` | `export_knowledge_base` | Export documents as a ZIP of markdown files preserving folder structure. |

### `app/routes/folders_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/folders` | `create_folder` |  |
| GET | `/folders` | `list_folders` | List all folders in a workspace (flat). Requires DOCUMENTS_READ permission. |
| GET | `/folders/{folder_id}` | `get_folder` | Get a single folder. Requires DOCUMENTS_READ permission. |
| GET | `/folders/{folder_id}/breadcrumb` | `get_folder_breadcrumb` | Get ancestor chain for breadcrumb display. Requires DOCUMENTS_READ permission. |
| PATCH | `/folders/{folder_id}/watched` | `stop_watching_folder` | Clear the watched flag from a folder's metadata. |
| PUT | `/folders/{folder_id}` | `update_folder` | Rename a folder. Requires DOCUMENTS_UPDATE permission. |
| PUT | `/folders/{folder_id}/move` | `move_folder` | Move a folder to a new parent. Requires DOCUMENTS_UPDATE permission. |
| PUT | `/folders/{folder_id}/reorder` | `reorder_folder` | Reorder a folder among its siblings via fractional indexing. Requires DOCUMENTS_UPDATE. |
| DELETE | `/folders/{folder_id}` | `delete_folder` | Mark documents for deletion and dispatch Celery to delete docs first, then folders. |
| PUT | `/documents/{document_id}/move` | `move_document` | Move a document to a folder (or root). Requires DOCUMENTS_UPDATE permission. |
| PUT | `/documents/bulk-move` | `bulk_move_documents` | Move multiple documents to a folder (or root). Requires DOCUMENTS_UPDATE permission. |

### `app/routes/gateway_webhook_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/slack/install` | `install_slack_gateway` |  |
| GET | `/slack/callback` | `slack_gateway_callback` |  |
| GET | `/discord/install` | `install_discord_gateway` |  |
| GET | `/discord/callback` | `discord_gateway_callback` |  |
| POST | `/webhooks/slack` | `slack_webhook` |  |
| POST | `/webhooks/telegram/{account_id}` | `telegram_webhook` |  |
| POST | `/bindings/start` | `start_binding` |  |
| GET | `/bindings` | `list_bindings` |  |
| GET | `/connections` | `list_connections` |  |
| GET | `/platforms` | `list_platforms` |  |
| GET | `/config` | `get_gateway_config` |  |
| PATCH | `/bindings/{binding_id}/workspace` | `update_binding_workspace` |  |
| PATCH | `/accounts/{account_id}/workspace` | `update_gateway_account_workspace` |  |
| DELETE | `/bindings/{binding_id}` | `delete_binding` |  |
| DELETE | `/accounts/{account_id}` | `delete_gateway_account` |  |
| POST | `/bindings/{binding_id}/resume` | `resume_external_chat_binding` |  |

### `app/routes/gateway_whatsapp_baileys_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/pair` | `request_pairing_code` |  |
| GET | `/health` | `bridge_health` |  |

### `app/routes/gateway_whatsapp_webhook_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `` | `verify_whatsapp_webhook` |  |
| POST | `` | `whatsapp_webhook` |  |

### `app/routes/google_calendar_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/google/calendar/connector/add` | `connect_calendar` |  |
| GET | `/auth/google/calendar/connector/reauth` | `reauth_calendar` | Initiate Google Calendar re-authentication for an existing connector. |
| GET | `/auth/google/calendar/connector/callback` | `calendar_callback` |  |

### `app/routes/google_drive_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/google/drive/connector/add` | `connect_drive` |  |
| GET | `/auth/google/drive/connector/reauth` | `reauth_drive` |  |
| GET | `/auth/google/drive/connector/callback` | `drive_callback` |  |
| GET | `/connectors/{connector_id}/google-drive/folders` | `list_google_drive_folders` |  |

### `app/routes/google_gmail_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/google/gmail/connector/add` | `connect_gmail` |  |
| GET | `/auth/google/gmail/connector/reauth` | `reauth_gmail` | Initiate Gmail re-authentication for an existing connector. |
| GET | `/auth/google/gmail/connector/callback` | `gmail_callback` |  |

### `app/routes/image_generation_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/image-generations` | `create_image_generation` |  |
| GET | `/image-generations` | `list_image_generations` |  |
| GET | `/image-generations/{image_gen_id}` | `get_image_generation` | Get a specific image generation by ID. |
| DELETE | `/image-generations/{image_gen_id}` | `delete_image_generation` | Delete an image generation record. |
| GET | `/image-generations/{image_gen_id}/image` | `serve_generated_image` |  |

### `app/routes/incentive_tasks_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `` | `get_incentive_tasks` |  |
| POST | `/{task_type}/complete` | `complete_task` |  |

### `app/routes/jira_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/jira/connector/add` | `connect_jira` |  |
| GET | `/auth/jira/connector/callback` | `jira_callback` |  |
| GET | `/auth/jira/connector/reauth` | `reauth_jira` | Initiate Jira re-authentication to upgrade OAuth scopes. |

### `app/routes/linear_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/linear/connector/add` | `connect_linear` |  |
| GET | `/auth/linear/connector/reauth` | `reauth_linear` | Initiate Linear re-authentication for an existing connector. |
| GET | `/auth/linear/connector/callback` | `linear_callback` |  |

### `app/routes/logs_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/logs` | `create_log` |  |
| GET | `/logs` | `read_logs` |  |
| GET | `/logs/{log_id}` | `read_log` |  |
| PUT | `/logs/{log_id}` | `update_log` |  |
| DELETE | `/logs/{log_id}` | `delete_log` |  |
| GET | `/logs/workspaces/{workspace_id}/summary` | `get_logs_summary` |  |

### `app/routes/luma_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/connectors/luma/add` | `add_luma_connector` |  |
| DELETE | `/connectors/luma` | `delete_luma_connector` |  |
| GET | `/connectors/luma/test` | `test_luma_connector` |  |

### `app/routes/mcp_oauth_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/mcp/{service}/connector/add` | `connect_mcp_service` |  |
| GET | `/auth/mcp/{service}/connector/callback` | `mcp_oauth_callback` |  |
| GET | `/auth/mcp/{service}/connector/reauth` | `reauth_mcp_service` |  |

### `app/routes/memory_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/users/me/memory` | `get_user_memory` |  |
| PUT | `/users/me/memory` | `update_user_memory` |  |
| POST | `/users/me/memory/reset` | `reset_user_memory` |  |

### `app/routes/model_connections_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/model-providers` | `list_model_providers` |  |
| GET | `/global-llm-config-status` | `global_llm_config_status` |  |
| GET | `/global-model-connections` | `list_global_connections` |  |
| GET | `/model-connections` | `list_connections` |  |
| POST | `/model-connections` | `create_connection` |  |
| POST | `/model-connections/discover-preview` | `preview_connection_models` |  |
| POST | `/model-connections/test-preview` | `test_preview_connection_model` |  |
| PUT | `/model-connections/{connection_id}` | `update_connection` |  |
| DELETE | `/model-connections/{connection_id}` | `delete_connection` |  |
| POST | `/model-connections/{connection_id}/verify` | `verify_model_connection` |  |
| POST | `/model-connections/{connection_id}/discover` | `discover_connection_models` |  |
| POST | `/model-connections/{connection_id}/models` | `add_manual_model` |  |
| PATCH | `/model-connections/{connection_id}/models` | `bulk_update_models` |  |
| PUT | `/models/{model_id}` | `update_model` |  |
| POST | `/models/{model_id}/test` | `test_connection_model` |  |
| GET | `/workspaces/{workspace_id}/model-roles` | `get_model_roles` |  |
| PUT | `/workspaces/{workspace_id}/model-roles` | `update_model_roles` |  |
| GET | `/workspaces/{workspace_id}/llm-setup-status` | `llm_setup_status` |  |

### `app/routes/model_list_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/models` | `list_available_models` |  |

### `app/routes/new_chat_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/threads` | `list_threads` |  |
| GET | `/threads/search` | `search_threads` |  |
| POST | `/threads` | `create_thread` |  |
| GET | `/threads/{thread_id}` | `get_thread_messages` |  |
| GET | `/threads/{thread_id}/full` | `get_thread_full` |  |
| PUT | `/threads/{thread_id}` | `update_thread` |  |
| DELETE | `/threads/{thread_id}` | `delete_thread` |  |
| PATCH | `/threads/{thread_id}/visibility` | `update_thread_visibility` |  |
| POST | `/threads/{thread_id}/snapshots` | `create_thread_snapshot` |  |
| GET | `/threads/{thread_id}/snapshots` | `list_thread_snapshots` |  |
| DELETE | `/threads/{thread_id}/snapshots/{snapshot_id}` | `delete_thread_snapshot` |  |
| POST | `/threads/{thread_id}/messages` | `append_message` |  |
| GET | `/threads/{thread_id}/messages` | `list_messages` |  |
| GET | `/agent/tools` | `list_agent_tools` | Return the list of built-in agent tools with their metadata. |
| POST | `/new_chat` | `handle_new_chat` |  |
| POST | `/threads/{thread_id}/cancel-active-turn` | `cancel_active_turn` |  |
| GET | `/threads/{thread_id}/turn-status` | `get_turn_status` |  |
| POST | `/threads/{thread_id}/regenerate` | `regenerate_response` |  |
| POST | `/threads/{thread_id}/resume` | `resume_chat` |  |

### `app/routes/notes_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/workspaces/{workspace_id}/notes` | `create_note` |  |
| GET | `/workspaces/{workspace_id}/notes` | `list_notes` |  |
| DELETE | `/workspaces/{workspace_id}/notes/{note_id}` | `delete_note` |  |

### `app/routes/notion_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/notion/connector/add` | `connect_notion` |  |
| GET | `/auth/notion/connector/reauth` | `reauth_notion` | Initiate Notion re-authentication for an existing connector. |
| GET | `/auth/notion/connector/callback` | `notion_callback` |  |

### `app/routes/obsidian_plugin_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/health` | `obsidian_health` | Return the API contract handshake; plugin caches it per onload. |
| POST | `/connect` | `obsidian_connect` | Register a vault, refresh an existing one, or adopt another device's row. |
| POST | `/sync` | `obsidian_sync` | Batch-upsert notes; returns per-note ack so the plugin can dequeue/retry. |
| POST | `/rename` | `obsidian_rename` | Apply a batch of vault rename events. |
| DELETE | `/notes` | `obsidian_delete_notes` | Soft-delete a batch of notes by vault-relative path. |
| GET | `/manifest` | `obsidian_manifest` | Return ``{path: {hash, mtime}}`` for the plugin's onload reconcile diff. |
| GET | `/stats` | `obsidian_stats` | Active-note count + last sync time for the web tile. |

### `app/routes/onedrive_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/onedrive/connector/add` | `connect_onedrive` | Initiate OneDrive OAuth flow. |
| GET | `/auth/onedrive/connector/reauth` | `reauth_onedrive` | Re-authenticate an existing OneDrive connector. |
| GET | `/auth/onedrive/connector/callback` | `onedrive_callback` | Handle OneDrive OAuth callback. |
| GET | `/connectors/{connector_id}/onedrive/folders` | `list_onedrive_folders` | List folders and files in user's OneDrive. |

### `app/routes/personal_access_tokens_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/pats` | `create_personal_access_token` |  |
| GET | `/pats` | `list_personal_access_tokens` |  |
| DELETE | `/pats/{pat_id}` | `delete_personal_access_token` |  |

### `app/routes/prompts_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/prompts` | `list_prompts` |  |
| POST | `/prompts` | `create_prompt` |  |
| PUT | `/prompts/{prompt_id}` | `update_prompt` |  |
| DELETE | `/prompts/{prompt_id}` | `delete_prompt` |  |
| GET | `/prompts/public` | `list_public_prompts` |  |
| POST | `/prompts/{prompt_id}/copy` | `copy_public_prompt` |  |

### `app/routes/public_chat_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/{share_token}` | `read_public_chat` |  |
| POST | `/{share_token}/clone` | `clone_public_chat` |  |
| GET | `/{share_token}/podcasts/{podcast_id}` | `get_public_podcast` |  |
| GET | `/{share_token}/podcasts/{podcast_id}/stream` | `stream_public_podcast` |  |
| GET | `/{share_token}/video-presentations/{video_presentation_id}` | `get_public_video_presentation` |  |
| GET | `/{share_token}/video-presentations/{video_presentation_id}/slides/{slide_number}/audio` | `stream_public_slide_audio` |  |
| GET | `/{share_token}/reports/{report_id}/preview` | `preview_public_report_pdf` |  |
| GET | `/{share_token}/reports/{report_id}/content` | `get_public_report_content` |  |

### `app/routes/rbac_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/permissions` | `list_all_permissions` |  |
| POST | `/workspaces/{workspace_id}/roles` | `create_role` |  |
| GET | `/workspaces/{workspace_id}/roles` | `list_roles` |  |
| GET | `/workspaces/{workspace_id}/roles/{role_id}` | `get_role` |  |
| PUT | `/workspaces/{workspace_id}/roles/{role_id}` | `update_role` |  |
| DELETE | `/workspaces/{workspace_id}/roles/{role_id}` | `delete_role` |  |
| GET | `/workspaces/{workspace_id}/members` | `list_members` |  |
| PUT | `/workspaces/{workspace_id}/members/{membership_id}` | `update_member_role` |  |
| DELETE | `/workspaces/{workspace_id}/members/me` | `leave_workspace` |  |
| DELETE | `/workspaces/{workspace_id}/members/{membership_id}` | `remove_member` |  |
| POST | `/workspaces/{workspace_id}/invites` | `create_invite` |  |
| GET | `/workspaces/{workspace_id}/invites` | `list_invites` |  |
| PUT | `/workspaces/{workspace_id}/invites/{invite_id}` | `update_invite` |  |
| DELETE | `/workspaces/{workspace_id}/invites/{invite_id}` | `revoke_invite` |  |
| GET | `/invites/{invite_code}/info` | `get_invite_info` |  |
| POST | `/invites/accept` | `accept_invite` |  |
| GET | `/workspaces/{workspace_id}/my-access` | `get_my_access` |  |

### `app/routes/reports_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/reports` | `read_reports` |  |
| GET | `/reports/{report_id}` | `read_report` |  |
| GET | `/reports/{report_id}/content` | `read_report_content` |  |
| PUT | `/reports/{report_id}/content` | `update_report_content` |  |
| GET | `/reports/{report_id}/preview` | `preview_report_pdf` |  |
| GET | `/reports/{report_id}/export` | `export_report` |  |
| DELETE | `/reports/{report_id}` | `delete_report` |  |

### `app/routes/sandbox_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/threads/{thread_id}/sandbox/download` | `download_sandbox_file` | Download a file from the Daytona sandbox associated with a chat thread. |

### `app/routes/search_source_connectors_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/github/repositories` | `list_github_repositories` |  |
| POST | `/search-source-connectors` | `create_search_source_connector` |  |
| GET | `/search-source-connectors` | `read_search_source_connectors` |  |
| GET | `/search-source-connectors/{connector_id}` | `read_search_source_connector` |  |
| PUT | `/search-source-connectors/{connector_id}` | `update_search_source_connector` |  |
| DELETE | `/search-source-connectors/{connector_id}` | `delete_search_source_connector` |  |
| POST | `/search-source-connectors/{connector_id}/index` | `index_connector_content` |  |
| POST | `/connectors/mcp` | `create_mcp_connector` |  |
| GET | `/connectors/mcp` | `list_mcp_connectors` |  |
| GET | `/connectors/mcp/{connector_id}` | `get_mcp_connector` |  |
| PUT | `/connectors/mcp/{connector_id}` | `update_mcp_connector` |  |
| DELETE | `/connectors/mcp/{connector_id}` | `delete_mcp_connector` |  |
| POST | `/connectors/mcp/test` | `test_mcp_server_connection` |  |
| GET | `/connectors/{connector_id}/drive-picker-token` | `get_drive_picker_token` | Return an OAuth access token + client ID for the Google Picker API. |
| POST | `/connectors/mcp/{connector_id}/trust-tool` | `trust_mcp_tool` |  |
| POST | `/connectors/mcp/{connector_id}/untrust-tool` | `untrust_mcp_tool` |  |

### `app/routes/slack_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/slack/connector/add` | `connect_slack` |  |
| GET | `/auth/slack/connector/callback` | `slack_callback` |  |
| GET | `/slack/connector/{connector_id}/channels` | `get_slack_channels` |  |

### `app/routes/stripe_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/create-credit-checkout-session` | `create_credit_checkout_session` | Create a Stripe Checkout Session for buying credit packs. |
| POST | `/webhook` | `stripe_webhook` | Handle Stripe webhooks and grant purchased credit after payment. |
| GET | `/finalize-checkout` | `finalize_checkout` | Synchronously fulfil a credit checkout session from the success page. |
| GET | `/credit-status` | `get_credit_status` | Return credit-buying availability and current balance for the frontend. |
| GET | `/credit-purchases` | `get_credit_purchases` | Return the authenticated user's credit purchase history. |
| GET | `/purchases` | `get_page_purchases` | Return the authenticated user's legacy page-purchase history (read-only). |
| POST | `/auto-reload/setup` | `create_auto_reload_setup_session` | Start a ``mode=setup`` checkout session to save a card for auto-reload. |
| GET | `/auto-reload` | `get_auto_reload_settings` | Return the user's auto-reload configuration and saved-card state. |
| PUT | `/auto-reload` | `update_auto_reload_settings` | Update auto-reload preferences. |

### `app/routes/team_memory_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/workspaces/{workspace_id}/memory` | `get_team_memory` |  |
| PUT | `/workspaces/{workspace_id}/memory` | `update_team_memory` |  |
| POST | `/workspaces/{workspace_id}/memory/reset` | `reset_team_memory` |  |

### `app/routes/teams_add_connector_route.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/auth/teams/connector/add` | `connect_teams` |  |
| GET | `/auth/teams/connector/callback` | `teams_callback` |  |

### `app/routes/users_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/me` | `get_current_user_profile` |  |
| PATCH | `/me` | `update_current_user_profile` |  |

### `app/routes/video_presentations_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/video-presentations` | `read_video_presentations` |  |
| GET | `/video-presentations/{video_presentation_id}` | `read_video_presentation` |  |
| DELETE | `/video-presentations/{video_presentation_id}` | `delete_video_presentation` |  |
| GET | `/video-presentations/{video_presentation_id}/slides/{slide_number}/audio` | `stream_slide_audio` |  |

### `app/routes/workspaces_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| POST | `/workspaces` | `create_workspace` |  |
| GET | `/workspaces` | `read_workspaces` |  |
| GET | `/workspaces/{workspace_id}` | `read_workspace` |  |
| PUT | `/workspaces/{workspace_id}` | `update_workspace` |  |
| PUT | `/workspaces/{workspace_id}/api-access` | `update_workspace_api_access` |  |
| DELETE | `/workspaces/{workspace_id}` | `delete_workspace` |  |
| GET | `/workspaces/{workspace_id}/snapshots` | `list_workspace_snapshots` |  |

### `app/routes/youtube_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/youtube/playlist-videos` | `get_playlist_videos` | Resolve a YouTube playlist URL into individual video URLs. |

### `app/routes/zero_context_routes.py`

| Method | Path | Function | Mô tả |
|---|---|---|---|
| GET | `/context` | `get_zero_context` |  |

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
