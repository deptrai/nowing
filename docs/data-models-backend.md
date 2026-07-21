# Nowing Backend - Data Models

**Ngày tạo:** 2026-07-21 16:59:34

## Tổng quan

Backend sử dụng SQLAlchemy với `DeclarativeBase` trong `app/db.py`. Hầu hết các model kế thừa `BaseModel` (có `id`) hoặc `TimestampMixin` (có `created_at`, `updated_at`). Alembic migrations nằm trong `alembic/versions/`.

## Các model chính

| File | Model | Base | Mô tả ngắn | Cột/relation đại diện |
|---|---|---|---|---|
| `app/db.py` | `Base` | DeclarativeBase |  |  |
| `app/db.py` | `BaseModel` | Base |  | id |
| `app/db.py` | `NewChatThread` | BaseModel, TimestampMixin |  | title, archived, updated_at, visibility, workspace_id, created_by_id, cloned_from_thread_id, cloned_from_snapshot_id |
| `app/db.py` | `NewChatMessage` | BaseModel, TimestampMixin |  | role, content, thread_id, author_id, turn_id, source, platform_metadata, thread |
| `app/db.py` | `ExternalChatAccount` | Base, TimestampMixin |  | id, platform, mode, owner_user_id, owner_workspace_id, is_system_account, encrypted_credentials, bot_username |
| `app/db.py` | `ExternalChatBinding` | Base, TimestampMixin |  | id, account_id, user_id, workspace_id, state, pairing_code, pairing_code_expires_at, external_peer_id |
| `app/db.py` | `ExternalChatInboundEvent` | Base, TimestampMixin |  | id, account_id, external_chat_binding_id, platform, event_dedupe_key, external_event_id, external_message_id, event_kind |
| `app/db.py` | `TokenUsage` | BaseModel, TimestampMixin |  | prompt_tokens, completion_tokens, total_tokens, cost_micros, model_breakdown, call_details, usage_type, thread_id |
| `app/db.py` | `PublicChatSnapshot` | BaseModel, TimestampMixin |  | thread_id, share_token, content_hash, snapshot_data, message_ids, created_by_user_id, thread, created_by |
| `app/db.py` | `ChatComment` | BaseModel, TimestampMixin |  | message_id, thread_id, parent_id, author_id, content, updated_at, message, thread |
| `app/db.py` | `ChatCommentMention` | BaseModel, TimestampMixin |  | comment_id, mentioned_user_id, comment, mentioned_user |
| `app/db.py` | `ChatSessionState` | BaseModel |  | thread_id, ai_responding_to_user_id, updated_at, thread, ai_responding_to_user |
| `app/db.py` | `Folder` | BaseModel, TimestampMixin |  | name, position, parent_id, workspace_id, created_by_id, updated_at, folder_metadata, parent |
| `app/db.py` | `Document` | BaseModel, TimestampMixin |  | title, document_type, document_metadata, content, content_hash, unique_identifier_hash, embedding, blocknote_document |
| `app/db.py` | `DocumentVersion` | BaseModel, TimestampMixin |  | document_id, version_number, source_markdown, content_hash, title, document |
| `app/db.py` | `Chunk` | BaseModel, TimestampMixin |  | content, embedding, position, document_id, document |
| `app/db.py` | `VideoPresentation` | BaseModel, TimestampMixin | Video presentation model for storing AI-generated video presentations. | title, slides, scene_codes, status, workspace_id, workspace, thread_id, thread |
| `app/db.py` | `Report` | BaseModel, TimestampMixin | Report model for storing generated reports (Markdown or Typst). | title, content, content_type, report_metadata, report_style, workspace_id, workspace, report_group_id |
| `app/db.py` | `Connection` | BaseModel, TimestampMixin |  | provider, base_url, api_key, extra, scope, enabled, workspace_id, user_id |
| `app/db.py` | `Model` | BaseModel, TimestampMixin |  | connection_id, model_id, display_name, source, supports_chat, max_input_tokens, supports_image_input, supports_tools |
| `app/db.py` | `ImageGeneration` | BaseModel, TimestampMixin |  | prompt, model, n, quality, size, style, response_format, image_gen_model_id |
| `app/db.py` | `Workspace` | BaseModel, TimestampMixin |  | name, description, citations_enabled, api_access_enabled, qna_custom_instructions, shared_memory_md, chat_model_id, image_gen_model_id |
| `app/db.py` | `SearchSourceConnector` | BaseModel, TimestampMixin |  | name, connector_type, is_indexable, last_indexed_at, config, enable_vision_llm, periodic_indexing_enabled, indexing_frequency_minutes |
| `app/db.py` | `Log` | BaseModel, TimestampMixin |  | level, status, message, source, log_metadata, workspace_id, workspace |
| `app/db.py` | `UserIncentiveTask` | BaseModel, TimestampMixin |  | user_id, task_type, credit_micros_awarded, completed_at, user |
| `app/db.py` | `PagePurchase` | Base, TimestampMixin | Tracks Stripe checkout sessions used to grant additional page credits. | id, user_id, stripe_checkout_session_id, stripe_payment_intent_id, quantity, pages_granted, amount_total, currency |
| `app/db.py` | `CreditPurchase` | Base, TimestampMixin | Tracks Stripe checkout sessions used to grant credit (USD micro-units). | id, user_id, stripe_checkout_session_id, stripe_payment_intent_id, quantity, credit_micros_granted, amount_total, currency |
| `app/db.py` | `WorkspaceRole` | BaseModel, TimestampMixin |  | name, description, permissions, is_default, is_system_role, workspace_id, workspace, memberships |
| `app/db.py` | `WorkspaceMembership` | BaseModel, TimestampMixin |  | user_id, workspace_id, role_id, is_owner, joined_at, invited_by_invite_id, user, workspace |
| `app/db.py` | `WorkspaceInvite` | BaseModel, TimestampMixin |  | invite_code, workspace_id, role_id, created_by_id, expires_at, max_uses, uses_count, is_active |
| `app/db.py` | `Prompt` | BaseModel, TimestampMixin |  | user_id, workspace_id, default_prompt_slug, name, prompt, mode, version, is_public |
| `app/db.py` | `AgentActionLog` | BaseModel | Append-only audit trail of every tool call dispatched by the agent. | thread_id, user_id, workspace_id, turn_id, tool_call_id, chat_turn_id, message_id, tool_name |
| `app/db.py` | `DocumentRevision` | BaseModel | Snapshot of a :class:`Document` row taken before a mutating tool call. | document_id, workspace_id, content_before, title_before, folder_id_before, chunks_before, metadata_before, created_by_turn_id |
| `app/db.py` | `FolderRevision` | BaseModel | Snapshot of a :class:`Folder` row taken before a mkdir / move. | folder_id, workspace_id, name_before, parent_id_before, position_before, created_by_turn_id, agent_action_id, created_at |
| `app/db.py` | `AgentPermissionRule` | BaseModel | Persistent permission rule consumed by :class:`PermissionMiddleware`. | workspace_id, user_id, thread_id, permission, pattern, action, created_at |
| `app/db.py` | `RefreshToken` | Base, TimestampMixin |  | id, user_id, user, token_hash, expires_at, revoked_at, absolute_expiry, family_id |
| `app/db.py` | `PersonalAccessToken` | BaseModel, TimestampMixin |  | user_id, user, token_hash, token_prefix, label, expires_at, last_used_at |
| `app/db.py` | `Run` | Base, TimestampMixin | One row per scraper-capability invocation, from either the agent door | id, workspace_id, user_id, thread_id, capability, origin, status, error |
| `app/db.py` | `ToolOutputSpill` | Base, TimestampMixin | Internal scratch store for main-agent context-editing spills. | id, workspace_id, thread_id, tool_name, content, char_count |
| `app/db.py` | `OAuthAccount` | SQLAlchemyBaseOAuthAccountTableUUID, Base |  |  |
| `app/db.py` | `User` | SQLAlchemyBaseUserTableUUID, Base |  | oauth_accounts, workspaces, notifications, workspace_memberships, created_invites, new_chat_threads, documents, folders |
| `app/db.py` | `User` | SQLAlchemyBaseUserTableUUID, Base |  | workspaces, notifications, workspace_memberships, created_invites, new_chat_threads, documents, folders, image_generations |
| `app/indexing_pipeline/cache/persistence/models.py` | `CachedEmbeddingSet` | BaseModel, TimestampMixin |  | markdown_sha256, embedding_model, embedding_dim, chunker_kind, chunker_version, storage_backend, storage_key, size_bytes |
| `app/file_storage/persistence/models.py` | `DocumentFile` | BaseModel, TimestampMixin | One stored file for a document (its original upload, or a derived copy). | document_id, workspace_id, kind, storage_backend, storage_key, original_filename, mime_type, size_bytes |
| `app/agents/chat/multi_agent_chat/shared/citations/models.py` | `CitationEntry` | BaseModel | A registered unit: ``n`` (the label), ``locator`` (identity), ``display`` (UI only). | n, source_type, locator, display |
| `app/podcasts/persistence/models.py` | `Podcast` | BaseModel, TimestampMixin | A podcast across its whole lifecycle: brief, transcript, audio, status. | title, status, source_content, spec, spec_version, podcast_transcript, storage_backend, storage_key |
| `app/etl_pipeline/cache/persistence/models.py` | `CachedParse` | BaseModel, TimestampMixin |  | source_sha256, etl_service, mode, parser_version, storage_backend, storage_key, size_bytes, content_type |
| `app/notifications/persistence/models.py` | `Notification` | BaseModel, TimestampMixin |  | user_id, workspace_id, type, title, message, read, notification_metadata, updated_at |

## Chiến lược migration

- Alembic được cấu hình trong `alembic.ini`, `alembic/env.py`.
- Các migration nằm trong `alembic/versions/` theo thứ tự số tăng dần.
- Lệnh chạy migration: `alembic upgrade head`.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
