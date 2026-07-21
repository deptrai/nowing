# SurfSense - Phân tích cây thư mục

**Ngày tạo:** 2026-07-21 16:59:34

## Tổng quan

Dự án SurfSense là monorepo gồm 7 phần chính. Mỗi phần có cấu trúc riêng nhưng cùng nằm dưới một repository.

## Cấu trúc repository

```
SurfSense/
├── README.md, CONTRIBUTING.md, LICENSE, VERSION
├── _bmad/                  # Cấu hình BMAD
├── _bmad-output/           # Artifact outputs
├── docker/                 # Docker Compose & scripts cài đặt
├── docs/                   # Tài liệu dự án được tạo
├── scripts/                # Script hỗ trợ
├── surfsense_backend/      # Backend FastAPI
├── surfsense_web/          # Web app Next.js
├── surfsense_browser_extension/  # Tiện ích trình duyệt Plasmo
├── surfsense_desktop/      # Ứng dụng Electron
├── surfsense_evals/        # Evaluation harness
├── surfsense_mcp/          # MCP server
└── surfsense_obsidian/     # Plugin Obsidian
```

## Cây thư mục từng phần

### surfsense_backend

```
surfsense_backend/
├── .dockerignore
├── .env
├── .env.example
├── .gitignore
├── .python-version
├── Dockerfile
├── alembic.ini
├── celery_worker.py
├── main.py
├── pyproject.toml
├── uv.lock
├── alembic/
│   ├── README
│   ├── env.py
│   ├── script.py.mako
│   ├── versions/
│   │   ├── 0_initial_schema.py
│   │   ├── 100_add_report_group_id.py
│   │   ├── 101_add_source_markdown_to_documents.py
│   │   ├── 102_add_enable_summary_to_connectors.py
│   │   ├── 103_add_last_login_to_user.py
│   │   ├── 104_add_notification_composite_indexes.py
│   │   ├── 105_add_chunks_document_id_index.py
│   │   ├── 106_add_minimax_to_litellmprovider_enum.py
│   │   ├── 107_add_video_presentations_table.py
│   │   ├── 108_cleanup_electric_sql_artifacts.py
│   │   ├── 109_add_folders_table.py
│   │   ├── 10_update_chattype_enum_to_qna_report_structure.py
│   │   ├── 110_add_onedrive_connector_enums.py
│   │   ├── 111_add_prompts_table.py
│   │   ├── 112_add_dropbox_connector_enums.py
│   │   ├── 113_add_prompt_library_schema.py
│   │   ├── 114_seed_default_prompts.py
│   │   ├── 115_add_page_purchases_table.py
│   │   ├── 116_create_zero_publication.py
│   │   ├── 117_optimize_zero_publication_column_lists.py
│   │   ├── 118_add_local_folder_sync_and_versioning.py
│   │   ├── 119_add_vision_llm_id_to_search_spaces.py
│   │   ├── 11_add_llm_config_table_and_relationships.py
│   │   ├── 120_add_vision_llm_configs_table.py
│   │   ├── 121_add_memory_md_columns.py
│   │   ├── 122_migrate_and_drop_old_memory_tables.py
│   │   ├── 123_add_enable_vision_llm_to_connectors.py
│   │   ├── 124_add_ai_file_sort_enabled.py
│   │   ├── 125_add_token_usage_table.py
│   │   ├── 126_add_premium_token_quota.py
│   │   ├── 127_add_report_content_type.py
│   │   ├── 128_seed_build_resume_prompt.py
│   │   ├── 129_obsidian_plugin_vault_identity.py
│   │   ├── 12_add_logs_table.py
│   │   ├── 130_add_agent_action_log.py
│   │   ├── 131_add_document_revisions.py
│   │   ├── 132_add_agent_permission_rules.py
│   │   ├── 133_drop_documents_content_hash_unique.py
│   │   ├── 134_relax_revision_fks.py
│   │   ├── 135_action_log_correlation_ids.py
│   │   ├── 136_new_chat_message_turn_id.py
│   │   ├── 137_unique_reverse_of_in_action_log.py
│   │   ├── 138_add_thread_auto_model_pinning_fields.py
│   │   ├── 139_add_user_to_zero_publication.py
│   │   ├── 13_add_jira_connector_enums.py
│   │   ├── 140_premium_tokens_to_credit_micros.py
│   │   ├── 141_unique_chat_message_turn_role.py
│   │   ├── 142_token_usage_message_id_unique.py
│   │   ├── 143_force_zero_publication_resync.py
│   │   ├── 144_add_automation_tables.py
│   │   ├── 145_add_automations_permissions_to_roles.py
│   │   ├── 146_drop_surfsense_docs_tables.py
│   │   ├── 147_add_event_to_automation_trigger_type.py
│   │   ├── 148_add_automation_runs_to_zero_publication.py
│   │   ├── 149_add_gateway_tables.py
│   │   ├── 14_add_confluence_connector_enums.py
│   │   ├── 150_add_slack_gateway_platform.py
│   │   ├── 151_add_discord_gateway_platform.py
│   │   ├── 152_add_document_files.py
│   │   ├── 153_restore_automation_runs_to_zero_publication.py
│   │   ├── 154_remove_document_summary_llm.py
│   │   ├── 155_reconcile_zero_publication.py
│   │   ├── 156_unify_credits_wallet.py
│   │   ├── 157_add_auto_reload_columns.py
│   │   ├── 158_evolve_podcasts_lifecycle.py
│   │   ├── 159_publish_podcasts_to_zero.py
│   │   ├── 15_add_clickup_connector_enums.py
│   │   ├── 160_add_model_connections.py
│   │   ├── 161_remove_legacy_model_configs.py
│   │   ├── 162_add_etl_cache_parses.py
│   │   ├── 163_add_embedding_cache_sets.py
│   │   ├── 164_remove_inactive_users.py
│   │   ├── 165_add_chunk_position.py
│   │   ├── 166_add_pat_and_api_access.py
│   │   ├── 167_publish_zero_authz_parent_tables.py
│   │   ├── 168_harden_refresh_token_schema.py
│   │   ├── 169_migrate_google_oauth_account_ids_to_sub.py
│   │   ├── 16_fix_connector_unique_constraint.py
│   │   ├── 170_rename_searchspace_to_workspace.py
│   │   ├── 171_add_runs_and_tool_output_spills.py
│   │   ├── 172_remove_ai_file_sort.py
│   │   ├── 173_add_runs_progress.py
│   │   ├── 174_add_llm_setup_completed_at.py
│   │   ├── 17_add_google_calendar_connector_enums.py
│   │   ├── 18_add_google_gmail_connector_enums.py
│   │   ├── 19_add_airtable_connector_enums.py
│   │   ├── 1_add_github_connector_enum.py
│   │   ├── 20_add_openrouter_to_litellmprovider_enum.py
│   │   ├── 21_add_luma_connector_enums.py
│   │   ├── 22_add_cometapi_to_litellmprovider_enum.py
│   │   ├── 23_associate_connectors_with_search_spaces.py
│   │   ├── 24_fix_null_chat_types.py
│   │   ├── 25_migrate_llm_configs_to_search_spaces.py
│   │   ├── 26_add_language_column_to_llm_configs.py
│   │   ├── 27_add_searxng_connector_enum.py
│   │   ├── 28_add_chinese_litellmprovider_enum.py
│   │   ├── 29_add_unique_identifier_hash_to_documents.py
│   │   ├── 2_add_linear_connector_enum.py
│   │   ├── 30_add_baidu_search_connector_enum.py
│   │   ├── 31_add_elasticsearch_connector_enums.py
│   │   ├── 32_add_periodic_indexing_fields.py
│   │   ├── 33_add_page_limits_to_user.py
│   │   ├── 34_add_podcast_staleness_detection.py
│   │   ├── 35_update_litellmprovider_enum_comprehensive.py
│   │   ├── 36_remove_fk_constraints_for_global_llm_configs.py
│   │   ├── 37_add_system_prompts_to_searchspaces.py
│   │   ├── 38_add_webcrawler_connector_enum.py
│   │   ├── 39_add_rbac_tables.py
│   │   ├── 3_add_linear_connector_to_documenttype_.py
│   │   ├── 40_move_llm_preferences_to_searchspace.py
│   │   ├── 41_backfill_rbac_for_existing_searchspaces.py
│   │   ├── 42_drop_user_search_space_preferences.py
│   │   ├── 43_add_blocknote_fields_to_documents.py
│   │   ├── 44_add_bookstack_connector_enums.py
│   │   ├── 45_add_updated_at_to_documents.py
│   │   ├── 46_remove_last_edited_at_from_documents.py
│   │   ├── 47_copy_created_at_to_updated_at.py
│   │   ├── 48_add_note_to_documenttype_enum.py
│   │   ├── 49_migrate_old_chats_to_new_chat.py
│   │   ├── 4_add_linkup_api_enum.py
│   │   ├── 50_remove_podcast_chat_columns.py
│   │   ├── 51_add_new_llm_config_table.py
│   │   ├── 52_rename_llm_preference_columns.py
│   │   ├── 53_cleanup_old_llm_configs.py
│   │   ├── 54_add_google_drive_connector_enums.py
│   │   ├── 55_rename_google_drive_connector_to_file.py
│   │   ├── 56_add_circleback_connector_enums.py
│   │   ├── 57_allow_multiple_connectors_per_type.py
│   │   ├── 58_unique_connector_name_per_space_user.py
│   │   ├── 59_add_teams_connector_enums.py
│   │   ├── 5_remove_title_char_limit.py
│   │   ├── 60_add_surfsense_docs_tables.py
│   │   ├── 61_add_chat_visibility_and_created_by.py
│   │   ├── 62_add_mcp_connector_type.py
│   │   ├── 63_allow_multiple_connectors_with_unique_.py
│   │   ├── 64_add_user_profile_columns.py
│   │   ├── 65_add_message_author_id.py
│   │   ├── 66_add_notifications_table_and_electric_replication.py
│   │   ├── 67_add_pg_trgm_index_for_document_title_search.py
│   │   ├── 68_add_chat_comments_table.py
│   │   ├── 69_add_chat_comment_mentions_table.py
│   │   ├── 6_change_podcast_content_to_transcript.py
│   │   ├── 70_add_comments_permissions_to_roles.py
│   │   ├── 71_add_comments_electric_replication.py
│   │   ├── 72_simplify_rbac_roles.py
│   │   ├── 73_add_user_memories_table.py
│   │   ├── 74_no_op.py
│   │   ├── 75_add_chat_session_state_table.py
│   │   ├── 76_add_live_collaboration_tables_electric_replication.py
│   │   ├── 77_add_thread_id_to_chat_comments.py
│   │   ├── 78_add_obsidian_connector.py
│   │   ├── 79_add_composio_connector_enums.py
│   │   ├── 7_remove_is_generated_column.py
│   │   ├── 80_add_user_incentive_tasks_table.py
│   │   ├── 81_add_public_chat_features.py
│   │   ├── 82_add_podcast_status_and_thread.py
│   │   ├── 83_add_reddit_follow_incentive_task.py
│   │   ├── 84_migrate_global_llm_configs_to_auto_mode.py
│   │   ├── 85_add_public_chat_snapshots_table.py
│   │   ├── 86_add_document_created_by.py
│   │   ├── 87_add_document_connector_id.py
│   │   ├── 88_make_podcast_transcript_nullable.py
│   │   ├── 89_make_podcast_file_location_nullable.py
│   │   ├── 8_add_content_hash_to_documents.py
│   │   ├── 90_add_public_sharing_permissions_to_roles.py
│   │   ├── 91_add_discord_join_incentive_task.py
│   │   ├── 92_add_refresh_tokens_table.py
│   │   ├── 93_add_image_generations_table.py
│   │   ├── 94_add_access_token_to_image_generations.py
│   │   ├── 95_add_document_status_column.py
│   │   ├── 96_add_shared_memories_table.py
│   │   ├── 97_add_github_models_to_litellmprovider_enum.py
│   │   ├── 98_add_user_id_to_llm_and_image_configs.py
│   │   ├── 99_add_reports_table.py
│   │   ├── 9_add_discord_connector_enum_and_documenttype.py
│   │   ├── e55302644c51_add_github_connector_to_documenttype_.py
├── app/
│   ├── __init__.py
│   ├── app.py
│   ├── celery_app.py
│   ├── db.py
│   ├── exceptions.py
│   ├── rate_limiter.py
│   ├── session_events.py
│   ├── users.py
│   ├── zero_publication.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── chat/
│   │   │   ├── __init__.py
│   │   │   ├── anonymous_chat/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent.py
│   │   │   ├── multi_agent_chat/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── constants.py
│   │   │   │   ├── main_agent/
│   │   │   │   ├── shared/
│   │   │   │   ├── subagents/
│   │   │   ├── runtime/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── checkpointer.py
│   │   │   │   ├── errors.py
│   │   │   │   ├── llm_config.py
│   │   │   │   ├── mention_resolver.py
│   │   │   │   ├── path_resolver.py
│   │   │   │   ├── prompt_caching.py
│   │   │   │   ├── referenced_chat_context/
│   │   │   │   ├── references/
│   │   │   ├── shared/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── context.py
│   │   │   │   ├── middleware/
│   │   │   │   ├── tools/
│   │   ├── video_presentation/
│   │   │   ├── __init__.py
│   │   │   ├── configuration.py
│   │   │   ├── graph.py
│   │   │   ├── nodes.py
│   │   │   ├── prompts.py
│   │   │   ├── state.py
│   │   │   ├── utils.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── context.py
│   │   ├── csrf.py
│   │   ├── session_cookies.py
│   ├── automations/
│   │   ├── __init__.py
│   │   ├── actions/
│   │   │   ├── __init__.py
│   │   │   ├── store.py
│   │   │   ├── types.py
│   │   │   ├── builtin/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent_task/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── automation.py
│   │   │   ├── run.py
│   │   │   ├── trigger.py
│   │   ├── dispatch/
│   │   │   ├── __init__.py
│   │   │   ├── errors.py
│   │   │   ├── inputs.py
│   │   │   ├── launch.py
│   │   │   ├── resolve.py
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── enums/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── automation_status.py
│   │   │   │   ├── run_status.py
│   │   │   │   ├── trigger_type.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── automation.py
│   │   │   │   ├── run.py
│   │   │   │   ├── trigger.py
│   │   ├── runtime/
│   │   │   ├── __init__.py
│   │   │   ├── executor.py
│   │   │   ├── repository.py
│   │   │   ├── retries.py
│   │   │   ├── step.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── automation.py
│   │   │   │   ├── run.py
│   │   │   │   ├── trigger.py
│   │   │   ├── definition/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── envelope.py
│   │   │   │   ├── execution.py
│   │   │   │   ├── inputs.py
│   │   │   │   ├── metadata.py
│   │   │   │   ├── plan_step.py
│   │   │   │   ├── trigger_spec.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── automation.py
│   │   │   ├── model_policy.py
│   │   │   ├── run.py
│   │   │   ├── trigger.py
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── execute_run.py
│   │   ├── templating/
│   │   │   ├── __init__.py
│   │   │   ├── allowlist.py
│   │   │   ├── context.py
│   │   │   ├── environment.py
│   │   │   ├── filters.py
│   │   │   ├── render.py
│   │   ├── triggers/
│   │   │   ├── __init__.py
│   │   │   ├── store.py
│   │   │   ├── types.py
│   │   │   ├── builtin/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── event/
│   │   │   │   ├── schedule/
│   ├── capabilities/
│   │   ├── __init__.py
│   │   ├── amazon/
│   │   │   ├── __init__.py
│   │   │   ├── scrape/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── billing.py
│   │   │   ├── events.py
│   │   │   ├── progress.py
│   │   │   ├── runs.py
│   │   │   ├── store.py
│   │   │   ├── types.py
│   │   │   ├── access/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent.py
│   │   │   │   ├── rate_limit.py
│   │   │   │   ├── rest.py
│   │   ├── google_maps/
│   │   │   ├── __init__.py
│   │   │   ├── reviews/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   │   ├── scrape/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   ├── google_search/
│   │   │   ├── __init__.py
│   │   │   ├── scrape/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   ├── instagram/
│   │   │   ├── __init__.py
│   │   │   ├── details/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   │   ├── scrape/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   ├── reddit/
│   │   │   ├── __init__.py
│   │   │   ├── scrape/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   ├── tiktok/
│   │   │   ├── __init__.py
│   │   │   ├── comments/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   │   ├── scrape/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   │   ├── trending/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   │   ├── user_search/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   ├── web/
│   │   │   ├── __init__.py
│   │   │   ├── crawl/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   ├── youtube/
│   │   │   ├── __init__.py
│   │   │   ├── comments/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   │   │   ├── scrape/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definition.py
│   │   │   │   ├── executor.py
│   │   │   │   ├── schemas.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── embedding_settings.py
│   │   ├── global_llm_config.example.yaml
│   │   ├── model_list_fallback.json
│   │   ├── uvicorn.py
│   │   ├── vision_model_list_fallback.json
│   ├── connectors/
│   │   ├── airtable_connector.py
│   │   ├── airtable_history.py
│   │   ├── bookstack_connector.py
│   │   ├── clickup_connector.py
│   │   ├── clickup_history.py
│   │   ├── composio_connector.py
│   │   ├── confluence_connector.py
│   │   ├── confluence_history.py
│   │   ├── discord_connector.py
│   │   ├── elasticsearch_connector.py
│   │   ├── exceptions.py
│   │   ├── github_connector.py
│   │   ├── google_calendar_connector.py
│   │   ├── google_gmail_connector.py
│   │   ├── linear_connector.py
│   │   ├── luma_connector.py
│   │   ├── notion_history.py
│   │   ├── slack_history.py
│   │   ├── teams_connector.py
│   │   ├── teams_history.py
│   │   ├── dropbox/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── content_extractor.py
│   │   │   ├── file_types.py
│   │   │   ├── folder_manager.py
│   │   ├── google_drive/
│   │   │   ├── __init__.py
│   │   │   ├── change_tracker.py
│   │   │   ├── client.py
│   │   │   ├── content_extractor.py
│   │   │   ├── credentials.py
│   │   │   ├── file_types.py
│   │   │   ├── folder_manager.py
│   │   ├── onedrive/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── content_extractor.py
│   │   │   ├── file_types.py
│   │   │   ├── folder_manager.py
│   ├── etl_pipeline/
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── etl_document.py
│   │   ├── etl_pipeline_service.py
│   │   ├── exceptions.py
│   │   ├── file_classifier.py
│   │   ├── picture_describer.py
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   ├── cached_extraction.py
│   │   │   ├── eligibility.py
│   │   │   ├── service.py
│   │   │   ├── settings.py
│   │   │   ├── eviction/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── policy.py
│   │   │   │   ├── task.py
│   │   │   ├── persistence/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── models.py
│   │   │   │   ├── repository.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── eviction_candidate.py
│   │   │   │   ├── parse_key.py
│   │   │   ├── storage/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── backend.py
│   │   │   │   ├── markdown_store.py
│   │   │   │   ├── object_keys.py
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── audio.py
│   │   │   ├── azure_doc_intelligence.py
│   │   │   ├── direct_convert.py
│   │   │   ├── docling.py
│   │   │   ├── llamacloud.py
│   │   │   ├── plaintext.py
│   │   │   ├── unstructured.py
│   │   │   ├── vision_llm.py
│   ├── event_bus/
│   │   ├── __init__.py
│   │   ├── bus.py
│   │   ├── catalog.py
│   │   ├── event.py
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── document_entered_folder.py
│   ├── file_storage/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── factory.py
│   │   ├── keys.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── settings.py
│   │   ├── backends/
│   │   │   ├── __init__.py
│   │   │   ├── azure.py
│   │   │   ├── base.py
│   │   │   ├── local.py
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   ├── models.py
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── accounts.py
│   │   ├── agent_invoke.py
│   │   ├── auth_invariant.py
│   │   ├── bindings.py
│   │   ├── byo_long_poll.py
│   │   ├── hitl_filter.py
│   │   ├── inbox.py
│   │   ├── inbox_processor.py
│   │   ├── inbox_worker.py
│   │   ├── pairing.py
│   │   ├── ratelimit.py
│   │   ├── registry.py
│   │   ├── runner.py
│   │   ├── thread_lock.py
│   │   ├── base/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py
│   │   │   ├── commands.py
│   │   │   ├── formatting.py
│   │   │   ├── identity.py
│   │   │   ├── translator.py
│   │   ├── discord/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py
│   │   │   ├── client.py
│   │   │   ├── commands.py
│   │   │   ├── intake.py
│   │   │   ├── translator.py
│   │   ├── slack/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py
│   │   │   ├── client.py
│   │   │   ├── commands.py
│   │   │   ├── translator.py
│   │   ├── telegram/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py
│   │   │   ├── client.py
│   │   │   ├── commands.py
│   │   │   ├── formatting.py
│   │   │   ├── translator.py
│   │   ├── whatsapp/
│   │   │   ├── __init__.py
│   │   │   ├── adapter_baileys.py
│   │   │   ├── adapter_cloud.py
│   │   │   ├── client_cloud.py
│   │   │   ├── commands.py
│   │   │   ├── credentials.py
│   │   │   ├── translator.py
│   │   │   ├── translator_baileys.py
│   ├── indexing_pipeline/
│   │   ├── __init__.py
│   │   ├── chunk_reconciler.py
│   │   ├── connector_document.py
│   │   ├── document_chunker.py
│   │   ├── document_embedder.py
│   │   ├── document_hashing.py
│   │   ├── document_persistence.py
│   │   ├── exceptions.py
│   │   ├── indexing_pipeline_service.py
│   │   ├── pipeline_logger.py
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── file_upload_adapter.py
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   ├── cached_indexing.py
│   │   │   ├── eligibility.py
│   │   │   ├── serialization.py
│   │   │   ├── service.py
│   │   │   ├── settings.py
│   │   │   ├── eviction/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── task.py
│   │   │   ├── persistence/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── models.py
│   │   │   │   ├── repository.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── embedding_key.py
│   │   │   │   ├── embedding_set.py
│   │   │   ├── storage/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── embedding_store.py
│   │   │   │   ├── object_keys.py
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── types.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── api.py
│   │   │   ├── schemas.py
│   │   │   ├── transform.py
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   ├── service/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── facade.py
│   │   │   ├── metadata.py
│   │   │   ├── handlers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auto_reload_failed.py
│   │   │   │   ├── comment_reply.py
│   │   │   │   ├── connector_indexing.py
│   │   │   │   ├── document_processing.py
│   │   │   │   ├── insufficient_credits.py
│   │   │   │   ├── mention.py
│   │   │   ├── messages/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auto_reload_failed.py
│   │   │   │   ├── connector_indexing.py
│   │   │   │   ├── document_processing.py
│   │   │   │   ├── insufficient_credits.py
│   │   │   │   ├── text.py
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── bootstrap.py
│   │   ├── metrics.py
│   │   ├── otel.py
│   ├── podcasts/
│   │   ├── __init__.py
│   │   ├── duration_limits.py
│   │   ├── service.py
│   │   ├── storage.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   ├── generation/
│   │   │   ├── __init__.py
│   │   │   ├── structured.py
│   │   │   ├── brief/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.py
│   │   │   │   ├── graph.py
│   │   │   │   ├── nodes.py
│   │   │   │   ├── propose.py
│   │   │   │   ├── state.py
│   │   │   ├── prompts/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── draft_segment.py
│   │   │   │   ├── plan_outline.py
│   │   │   │   ├── speakers.py
│   │   │   ├── transcript/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.py
│   │   │   │   ├── graph.py
│   │   │   │   ├── nodes.py
│   │   │   │   ├── planning.py
│   │   │   │   ├── state.py
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── repository.py
│   │   │   ├── enums/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── podcast_status.py
│   │   ├── rendering/
│   │   │   ├── __init__.py
│   │   │   ├── cache.py
│   │   │   ├── errors.py
│   │   │   ├── merge.py
│   │   │   ├── renderer.py
│   │   ├── resolution/
│   │   │   ├── __init__.py
│   │   │   ├── language.py
│   │   │   ├── voices.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── spec.py
│   │   │   ├── transcript.py
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── draft.py
│   │   │   ├── render.py
│   │   │   ├── runtime.py
│   │   ├── tts/
│   │   │   ├── __init__.py
│   │   │   ├── audio.py
│   │   │   ├── errors.py
│   │   │   ├── factory.py
│   │   │   ├── port.py
│   │   │   ├── request.py
│   │   │   ├── adapters/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── kokoro.py
│   │   │   │   ├── litellm.py
│   │   ├── voices/
│   │   │   ├── __init__.py
│   │   │   ├── catalog.py
│   │   │   ├── preview.py
│   │   │   ├── provider.py
│   │   │   ├── voice.py
│   │   │   ├── data/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── azure.py
│   │   │   │   ├── kokoro.py
│   │   │   │   ├── languages.py
│   │   │   │   ├── openai.py
│   │   │   │   ├── vertex.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── system_defaults.py
│   ├── proprietary/
│   │   ├── LICENSE
│   │   ├── __init__.py
│   │   ├── platforms/
│   │   │   ├── __init__.py
│   │   │   ├── amazon/
│   │   │   │   ├── README.md
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fetch.py
│   │   │   │   ├── locale.py
│   │   │   │   ├── parsers.py
│   │   │   │   ├── schemas.py
│   │   │   │   ├── scraper.py
│   │   │   │   ├── url_resolver.py
│   │   │   ├── google_maps/
│   │   │   │   ├── README.md
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fetch.py
│   │   │   │   ├── parsers.py
│   │   │   │   ├── reviews.py
│   │   │   │   ├── schemas.py
│   │   │   │   ├── scraper.py
│   │   │   │   ├── url_resolver.py
│   │   │   ├── google_search/
│   │   │   │   ├── README.md
│   │   │   │   ├── __init__.py
│   │   │   │   ├── captcha.py
│   │   │   │   ├── fetch.py
│   │   │   │   ├── parsers.py
│   │   │   │   ├── pool_store.py
│   │   │   │   ├── query_builder.py
│   │   │   │   ├── schemas.py
│   │   │   │   ├── scraper.py
│   │   │   ├── instagram/
│   │   │   │   ├── README.md
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fetch.py
│   │   │   │   ├── parsers.py
│   │   │   │   ├── schemas.py
│   │   │   │   ├── scraper.py
│   │   │   │   ├── url_resolver.py
│   │   │   ├── reddit/
│   │   │   │   ├── README.md
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fetch.py
│   │   │   │   ├── parsers.py
│   │   │   │   ├── schemas.py
│   │   │   │   ├── scraper.py
│   │   │   │   ├── url_resolver.py
│   │   │   ├── tiktok/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── orchestrator.py
│   │   │   │   ├── extraction/
│   │   │   │   ├── flows/
│   │   │   │   ├── schemas/
│   │   │   │   ├── session/
│   │   │   │   ├── targets/
│   │   │   ├── youtube/
│   │   │   │   ├── README.md
│   │   │   │   ├── __init__.py
│   │   │   │   ├── comments.py
│   │   │   │   ├── innertube.py
│   │   │   │   ├── parsers.py
│   │   │   │   ├── schemas.py
│   │   │   │   ├── scraper.py
│   │   │   │   ├── search_filters.py
│   │   │   │   ├── subtitles.py
│   │   │   │   ├── url_resolver.py
│   │   ├── web_crawler/
│   │   │   ├── README.md
│   │   │   ├── __init__.py
│   │   │   ├── captcha.py
│   │   │   ├── connector.py
│   │   │   ├── site_crawler.py
│   │   │   ├── stealth.py
│   │   │   ├── url_policy.py
│   │   │   ├── testbench/
│   │   │   │   ├── README.md
│   │   │   │   ├── __init__.py
│   │   │   │   ├── __main__.py
│   │   │   │   ├── core.py
│   │   │   │   ├── suite_extraction.py
│   │   │   │   ├── suite_stealth.py
│   │   │   │   ├── results/
│   ├── retriever/
│   │   ├── __init__.py
│   │   ├── chunks_hybrid_search.py
│   │   ├── documents_hybrid_search.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── agent_action_log_route.py
│   │   ├── agent_flags_route.py
│   │   ├── agent_permissions_route.py
│   │   ├── agent_revert_route.py
│   │   ├── airtable_add_connector_route.py
│   │   ├── anonymous_chat_routes.py
│   │   ├── auth_routes.py
│   │   ├── chat_comments_routes.py
│   │   ├── circleback_webhook_route.py
│   │   ├── clickup_add_connector_route.py
│   │   ├── composio_routes.py
│   │   ├── confluence_add_connector_route.py
│   │   ├── discord_add_connector_route.py
│   │   ├── documents_routes.py
│   │   ├── dropbox_add_connector_route.py
│   │   ├── editor_routes.py
│   │   ├── export_routes.py
│   │   ├── folders_routes.py
│   │   ├── gateway_webhook_routes.py
│   │   ├── gateway_whatsapp_baileys_routes.py
│   │   ├── gateway_whatsapp_webhook_routes.py
│   │   ├── google_calendar_add_connector_route.py
│   │   ├── google_drive_add_connector_route.py
│   │   ├── google_gmail_add_connector_route.py
│   │   ├── image_generation_routes.py
│   │   ├── incentive_tasks_routes.py
│   │   ├── jira_add_connector_route.py
│   │   ├── linear_add_connector_route.py
│   │   ├── logs_routes.py
│   │   ├── luma_add_connector_route.py
│   │   ├── mcp_oauth_route.py
│   │   ├── memory_routes.py
│   │   ├── model_connections_routes.py
│   │   ├── model_list_routes.py
│   │   ├── new_chat_routes.py
│   │   ├── notes_routes.py
│   │   ├── notion_add_connector_route.py
│   │   ├── oauth_connector_base.py
│   │   ├── obsidian_plugin_routes.py
│   │   ├── onedrive_add_connector_route.py
│   │   ├── personal_access_tokens_routes.py
│   │   ├── prompts_routes.py
│   │   ├── public_chat_routes.py
│   │   ├── rbac_routes.py
│   │   ├── reports_routes.py
│   │   ├── sandbox_routes.py
│   │   ├── search_source_connectors_routes.py
│   │   ├── slack_add_connector_route.py
│   │   ├── stripe_routes.py
│   │   ├── team_memory_routes.py
│   │   ├── teams_add_connector_route.py
│   │   ├── users_routes.py
│   │   ├── video_presentations_routes.py
│   │   ├── workspaces_routes.py
│   │   ├── youtube_routes.py
│   │   ├── zero_context_routes.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── airtable_auth_credentials.py
│   │   ├── atlassian_auth_credentials.py
│   │   ├── auth.py
│   │   ├── base.py
│   │   ├── chat_comments.py
│   │   ├── chat_session_state.py
│   │   ├── chunks.py
│   │   ├── clickup_auth_credentials.py
│   │   ├── discord_auth_credentials.py
│   │   ├── documents.py
│   │   ├── folders.py
│   │   ├── google_drive.py
│   │   ├── image_generation.py
│   │   ├── incentive_tasks.py
│   │   ├── linear_auth_credentials.py
│   │   ├── logs.py
│   │   ├── model_connections.py
│   │   ├── new_chat.py
│   │   ├── notion_auth_credentials.py
│   │   ├── obsidian_plugin.py
│   │   ├── onedrive_auth_credentials.py
│   │   ├── pat.py
│   │   ├── prompts.py
│   │   ├── rbac_schemas.py
│   │   ├── reports.py
│   │   ├── search_source_connector.py
│   │   ├── slack_auth_credentials.py
│   │   ├── stripe.py
│   │   ├── teams_auth_credentials.py
│   │   ├── users.py
│   │   ├── video_presentations.py
│   │   ├── workspace.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auto_model_pin_service.py
│   │   ├── auto_reload_service.py
│   │   ├── billable_calls.py
│   │   ├── chat_comments_service.py
│   │   ├── chat_session_state_service.py
│   │   ├── composio_service.py
│   │   ├── connector_service.py
│   │   ├── docling_service.py
│   │   ├── etl_credit_service.py
│   │   ├── export_service.py
│   │   ├── folder_service.py
│   │   ├── global_model_catalog.py
│   │   ├── image_gen_router_service.py
│   │   ├── kokoro_tts_service.py
│   │   ├── llm_error_adapter.py
│   │   ├── llm_router_service.py
│   │   ├── llm_service.py
│   │   ├── model_capabilities.py
│   │   ├── model_connection_service.py
│   │   ├── model_list_service.py
│   │   ├── model_resolver.py
│   │   ├── new_streaming_service.py
│   │   ├── obsidian_plugin_indexer.py
│   │   ├── openrouter_integration_service.py
│   │   ├── openrouter_model_normalizer.py
│   │   ├── platform_scrape_credit_service.py
│   │   ├── pricing_registration.py
│   │   ├── provider_capabilities.py
│   │   ├── provider_registry.py
│   │   ├── public_chat_service.py
│   │   ├── quality_score.py
│   │   ├── quota_checked_vision_llm.py
│   │   ├── requesty_model_normalizer.py
│   │   ├── reranker_service.py
│   │   ├── revert_service.py
│   │   ├── stt_service.py
│   │   ├── task_dispatcher.py
│   │   ├── task_logging_service.py
│   │   ├── token_quota_service.py
│   │   ├── token_tracking_service.py
│   │   ├── turnstile_service.py
│   │   ├── user_tool_allowlist.py
│   │   ├── wallet_credit.py
│   │   ├── web_crawl_credit_service.py
│   │   ├── confluence/
│   │   │   ├── __init__.py
│   │   │   ├── kb_sync_service.py
│   │   │   ├── tool_metadata_service.py
│   │   ├── dropbox/
│   │   │   ├── __init__.py
│   │   │   ├── kb_sync_service.py
│   │   ├── gmail/
│   │   │   ├── __init__.py
│   │   │   ├── kb_sync_service.py
│   │   │   ├── tool_metadata_service.py
│   │   ├── google_calendar/
│   │   │   ├── __init__.py
│   │   │   ├── kb_sync_service.py
│   │   │   ├── tool_metadata_service.py
│   │   ├── google_drive/
│   │   │   ├── __init__.py
│   │   │   ├── kb_sync_service.py
│   │   │   ├── tool_metadata_service.py
│   │   ├── linear/
│   │   │   ├── __init__.py
│   │   │   ├── kb_sync_service.py
│   │   │   ├── tool_metadata_service.py
│   │   ├── mcp_oauth/
│   │   │   ├── __init__.py
│   │   │   ├── discovery.py
│   │   │   ├── registry.py
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── prompts.py
│   │   │   ├── rewrite.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── validation.py
│   │   ├── notion/
│   │   │   ├── __init__.py
│   │   │   ├── kb_sync_service.py
│   │   │   ├── tool_metadata_service.py
│   │   ├── onedrive/
│   │   │   ├── __init__.py
│   │   │   ├── kb_sync_service.py
│   │   ├── streaming/
│   │   │   ├── __init__.py
│   │   │   ├── interrupt_correlation.py
│   │   │   ├── service.py
│   │   │   ├── emitter/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── emitter.py
│   │   │   │   ├── registry.py
│   │   │   ├── envelope/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── identifiers.py
│   │   │   │   ├── sse.py
│   │   │   ├── events/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── action_log.py
│   │   │   │   ├── data.py
│   │   │   │   ├── error.py
│   │   │   │   ├── interrupt.py
│   │   │   │   ├── lifecycle.py
│   │   │   │   ├── reasoning.py
│   │   │   │   ├── source.py
│   │   │   │   ├── subagent_lifecycle.py
│   │   │   │   ├── text.py
│   │   │   │   ├── tool.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── composio_indexer.py
│   │   ├── celery_tasks/
│   │   │   ├── __init__.py
│   │   │   ├── auto_reload_task.py
│   │   │   ├── connector_tasks.py
│   │   │   ├── document_reindex_tasks.py
│   │   │   ├── document_tasks.py
│   │   │   ├── gateway_tasks.py
│   │   │   ├── obsidian_tasks.py
│   │   │   ├── refresh_token_cleanup_task.py
│   │   │   ├── schedule_checker_task.py
│   │   │   ├── stale_notification_cleanup_task.py
│   │   │   ├── stripe_reconciliation_task.py
│   │   │   ├── video_presentation_tasks.py
│   │   ├── chat/
│   │   │   ├── content_builder.py
│   │   │   ├── llm_history_normalizer.py
│   │   │   ├── message_parts_normalizer.py
│   │   │   ├── persistence.py
│   │   │   ├── streaming/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent/
│   │   │   │   ├── context/
│   │   │   │   ├── contract/
│   │   │   │   ├── errors/
│   │   │   │   ├── flows/
│   │   │   │   ├── graph_stream/
│   │   │   │   ├── handlers/
│   │   │   │   ├── helpers/
│   │   │   │   ├── relay/
│   │   │   │   ├── shared/
│   │   ├── connector_indexers/
│   │   │   ├── __init__.py
│   │   │   ├── airtable_indexer.py
│   │   │   ├── base.py
│   │   │   ├── bookstack_indexer.py
│   │   │   ├── clickup_indexer.py
│   │   │   ├── confluence_indexer.py
│   │   │   ├── discord_indexer.py
│   │   │   ├── dropbox_indexer.py
│   │   │   ├── elasticsearch_indexer.py
│   │   │   ├── github_indexer.py
│   │   │   ├── google_calendar_indexer.py
│   │   │   ├── google_drive_indexer.py
│   │   │   ├── google_gmail_indexer.py
│   │   │   ├── linear_indexer.py
│   │   │   ├── local_folder_indexer.py
│   │   │   ├── luma_indexer.py
│   │   │   ├── notion_indexer.py
│   │   │   ├── onedrive_indexer.py
│   │   │   ├── slack_indexer.py
│   │   │   ├── teams_indexer.py
│   │   ├── document_processors/
│   │   │   ├── __init__.py
│   │   │   ├── _direct_converters.py
│   │   │   ├── _helpers.py
│   │   │   ├── _save.py
│   │   │   ├── base.py
│   │   │   ├── circleback_processor.py
│   │   │   ├── extension_processor.py
│   │   │   ├── file_processors.py
│   │   │   ├── markdown_processor.py
│   ├── templates/
│   │   ├── __init__.py
│   │   ├── export_helpers.py
│   │   ├── report_html.css
│   │   ├── report_pdf.typst
│   ├── utils/
│   │   ├── async_retry.py
│   │   ├── blocknote_to_markdown.py
│   │   ├── chat_comments.py
│   │   ├── connector_naming.py
│   │   ├── content_utils.py
│   │   ├── document_converters.py
│   │   ├── document_versioning.py
│   │   ├── file_extensions.py
│   │   ├── google_credentials.py
│   │   ├── indexing_locks.py
│   │   ├── notion_utils.py
│   │   ├── oauth_security.py
│   │   ├── pat.py
│   │   ├── perf.py
│   │   ├── periodic_scheduler.py
│   │   ├── proxy_config.py
│   │   ├── rbac.py
│   │   ├── refresh_tokens.py
│   │   ├── signed_image_urls.py
│   │   ├── user_message_multimodal.py
│   │   ├── validators.py
│   │   ├── captcha/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── solvers.py
│   │   ├── crawl/
│   │   │   ├── __init__.py
│   │   │   ├── classifier.py
│   │   │   ├── contacts.py
│   │   ├── proxy/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── rotation.py
│   │   │   ├── providers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── custom.py
│   │   │   │   ├── dataimpulse.py
├── scripts/
│   ├── check_migration_flow.py
│   ├── check_zero_publication_bootstrap.py
│   ├── create_sandbox_snapshot.py
│   ├── e2e_amazon_scraper.py
│   ├── e2e_google_maps_deep.py
│   ├── e2e_google_maps_scraper.py
│   ├── e2e_google_search.py
│   ├── e2e_instagram_scraper.py
│   ├── e2e_phase3_crawl_billing.py
│   ├── e2e_reddit_scraper.py
│   ├── e2e_tiktok_scrape.py
│   ├── e2e_youtube_scraper.py
│   ├── register_webhook.py
│   ├── revoke_refresh_tokens_cutover.py
│   ├── scale_google_search.py
│   ├── stress_google_search.py
│   ├── verify_chat_image_capability.py
│   ├── docker/
│   │   ├── entrypoint.e2e.sh
│   │   ├── entrypoint.sh
│   ├── whatsapp-bridge/
│   │   ├── Dockerfile
│   │   ├── bridge.js
│   │   ├── package-lock.json
│   │   ├── package.json
├── tests/
│   ├── README.md
│   ├── __init__.py
│   ├── conftest.py
│   ├── e2e/
│   │   ├── README.md
│   │   ├── __init__.py
│   │   ├── auth_mint.py
│   │   ├── run_backend.py
│   │   ├── run_celery.py
│   │   ├── fakes/
│   │   │   ├── __init__.py
│   │   │   ├── binary_loader.py
│   │   │   ├── chat_llm.py
│   │   │   ├── clickup_module.py
│   │   │   ├── composio_module.py
│   │   │   ├── confluence_indexer.py
│   │   │   ├── confluence_oauth.py
│   │   │   ├── docling_service.py
│   │   │   ├── dropbox_api.py
│   │   │   ├── embeddings.py
│   │   │   ├── jira_module.py
│   │   │   ├── linear_module.py
│   │   │   ├── llm.py
│   │   │   ├── mcp_oauth_runtime.py
│   │   │   ├── mcp_runtime.py
│   │   │   ├── native_google.py
│   │   │   ├── notion_mcp_module.py
│   │   │   ├── notion_module.py
│   │   │   ├── onedrive_graph.py
│   │   │   ├── slack_module.py
│   │   │   ├── fixtures/
│   │   │   │   ├── calendar_events.json
│   │   │   │   ├── clickup_tasks.json
│   │   │   │   ├── confluence_pages.json
│   │   │   │   ├── drive_files.json
│   │   │   │   ├── dropbox_files.json
│   │   │   │   ├── gmail_messages.json
│   │   │   │   ├── jira_issues.json
│   │   │   │   ├── linear_issues.json
│   │   │   │   ├── notion_pages.json
│   │   │   │   ├── onedrive_files.json
│   │   │   │   ├── slack_messages.json
│   │   │   │   ├── binary/
│   │   ├── fixtures/
│   │   │   ├── global_llm_config.yaml
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── scenario.py
│   ├── fixtures/
│   │   ├── empty.pdf
│   │   ├── sample.md
│   │   ├── sample.pdf
│   │   ├── sample.txt
│   │   ├── tiktok/
│   │   │   ├── listing_item.json
│   │   │   ├── video_item_struct.json
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_auth_transport_invariant.py
│   │   ├── test_connector_index_authz.py
│   │   ├── test_document_versioning.py
│   │   ├── test_obsidian_plugin_routes.py
│   │   ├── test_pat_fail_closed_authz.py
│   │   ├── test_zero_authz_context.py
│   │   ├── agents/
│   │   │   ├── multi_agent_chat/
│   │   │   │   ├── test_agent_turn.py
│   │   │   │   ├── test_kb_filesystem_cloud.py
│   │   │   │   ├── test_kb_filesystem_desktop.py
│   │   │   │   ├── test_web_search_delegation.py
│   │   │   │   ├── shared/
│   │   │   │   ├── subagents/
│   │   ├── automations/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_checkpointer_cross_loop.py
│   │   │   ├── actions/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── builtin/
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   ├── chat/
│   │   │   ├── __init__.py
│   │   │   ├── test_append_message_recovery.py
│   │   │   ├── test_message_id_sse.py
│   │   │   ├── test_persistence.py
│   │   │   ├── test_thread_visibility.py
│   │   ├── composio/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_drive_folders_route.py
│   │   │   ├── test_oauth_callback.py
│   │   ├── document_upload/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_document_upload.py
│   │   │   ├── test_etl_credits.py
│   │   │   ├── test_stripe_credit_purchases.py
│   │   │   ├── test_upload_limits.py
│   │   ├── etl_pipeline/
│   │   │   ├── cache/
│   │   │   │   ├── conftest.py
│   │   │   │   ├── test_cached_extraction.py
│   │   │   │   ├── test_cached_parse_repository.py
│   │   │   │   ├── test_etl_cache_service.py
│   │   │   │   ├── test_eviction_task.py
│   │   │   │   ├── test_markdown_store.py
│   │   ├── google_unification/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_calendar_indexer_credentials.py
│   │   │   ├── test_drive_indexer_credentials.py
│   │   │   ├── test_gmail_indexer_credentials.py
│   │   │   ├── test_hybrid_search_type_filtering.py
│   │   │   ├── test_search_includes_legacy_docs.py
│   │   ├── harness/
│   │   │   ├── __init__.py
│   │   │   ├── test_scripted_harness.py
│   │   ├── indexing_pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── test_calendar_pipeline.py
│   │   │   ├── test_drive_pipeline.py
│   │   │   ├── test_dropbox_pipeline.py
│   │   │   ├── test_gmail_pipeline.py
│   │   │   ├── test_index_batch.py
│   │   │   ├── test_index_document.py
│   │   │   ├── test_index_editions.py
│   │   │   ├── test_local_folder_pipeline.py
│   │   │   ├── test_mark_connector_documents_failed.py
│   │   │   ├── test_migrate_legacy_docs.py
│   │   │   ├── test_onedrive_pipeline.py
│   │   │   ├── test_prepare_for_indexing.py
│   │   │   ├── adapters/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_file_upload_adapter.py
│   │   │   ├── cache/
│   │   │   │   ├── conftest.py
│   │   │   │   ├── test_cached_embedding_repository.py
│   │   │   │   ├── test_embedding_cache_service.py
│   │   │   │   ├── test_embedding_store.py
│   │   ├── notifications/
│   │   │   ├── conftest.py
│   │   │   ├── test_base_handler.py
│   │   │   ├── test_comment_reply_handler.py
│   │   │   ├── test_connector_indexing_handler.py
│   │   │   ├── test_document_processing_handler.py
│   │   │   ├── test_inbox_api.py
│   │   │   ├── test_insufficient_credits_handler.py
│   │   │   ├── test_mention_handler.py
│   │   ├── podcasts/
│   │   │   ├── conftest.py
│   │   │   ├── test_brief_gate.py
│   │   │   ├── test_cancel.py
│   │   │   ├── test_create.py
│   │   │   ├── test_draft_task.py
│   │   │   ├── test_public_stream.py
│   │   │   ├── test_regeneration.py
│   │   │   ├── test_render_task.py
│   │   │   ├── test_scoping.py
│   │   │   ├── test_streaming.py
│   │   │   ├── test_task_failure.py
│   │   │   ├── test_voice_preview.py
│   │   │   ├── test_voices.py
│   │   ├── retriever/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_optimized_chunk_retriever.py
│   │   │   ├── test_optimized_doc_retriever.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_error_contract.py
│   │   ├── test_obsidian_plugin_indexer.py
│   │   ├── test_pat_fail_closed_static.py
│   │   ├── test_zero_authz_static.py
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── test_import_all.py
│   │   │   ├── test_video_presentation_graph.py
│   │   │   ├── chat/
│   │   │   │   ├── runtime/
│   │   │   ├── multi_agent_chat/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_mcp_allowlist_fallback.py
│   │   │   │   ├── test_mcp_discovery_migration.py
│   │   │   │   ├── test_prompt_resources.py
│   │   │   │   ├── test_subagent_composition.py
│   │   │   │   ├── test_web_search_removed.py
│   │   │   │   ├── middleware/
│   │   │   │   ├── shared/
│   │   │   │   ├── subagents/
│   │   │   ├── new_chat/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_action_log.py
│   │   │   │   ├── test_agent_cache.py
│   │   │   │   ├── test_busy_mutex.py
│   │   │   │   ├── test_compaction.py
│   │   │   │   ├── test_context_editing.py
│   │   │   │   ├── test_dedup_tool_calls.py
│   │   │   │   ├── test_default_permissions_layering.py
│   │   │   │   ├── test_desktop_safety_rules.py
│   │   │   │   ├── test_doom_loop.py
│   │   │   │   ├── test_feature_flags.py
│   │   │   │   ├── test_hitl_auto_approve.py
│   │   │   │   ├── test_memory_response_content.py
│   │   │   │   ├── test_mention_resolver.py
│   │   │   │   ├── test_noop_injection.py
│   │   │   │   ├── test_otel_span.py
│   │   │   │   ├── test_path_resolver.py
│   │   │   │   ├── test_permissions.py
│   │   │   │   ├── test_plugin_loader.py
│   │   │   │   ├── test_prompt_caching.py
│   │   │   │   ├── middleware/
│   │   │   │   ├── prompts/
│   │   │   │   ├── tools/
│   │   ├── automations/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_definition_types.py
│   │   │   ├── test_import_registrations.py
│   │   │   ├── test_persistence_enums.py
│   │   │   ├── test_stores.py
│   │   │   ├── actions/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── builtin/
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   ├── dispatch/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_errors.py
│   │   │   │   ├── test_inputs.py
│   │   │   ├── runtime/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_execute_step.py
│   │   │   │   ├── test_executor_action_ctx.py
│   │   │   │   ├── test_retries.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api/
│   │   │   │   ├── definition/
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_automation_service_policy.py
│   │   │   │   ├── test_model_policy.py
│   │   │   ├── templating/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_context.py
│   │   │   │   ├── test_environment.py
│   │   │   │   ├── test_filters.py
│   │   │   │   ├── test_render.py
│   │   │   ├── triggers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── builtin/
│   │   ├── capabilities/
│   │   │   ├── __init__.py
│   │   │   ├── test_billing.py
│   │   │   ├── test_registry.py
│   │   │   ├── test_run_truncation.py
│   │   │   ├── access/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_agent_tools.py
│   │   │   │   ├── test_rate_limit.py
│   │   │   │   ├── test_rest_router.py
│   │   │   ├── amazon/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_registry.py
│   │   │   │   ├── scrape/
│   │   │   ├── google_maps/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_registry.py
│   │   │   │   ├── reviews/
│   │   │   │   ├── scrape/
│   │   │   ├── instagram/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_executor.py
│   │   │   │   ├── test_registry.py
│   │   │   │   ├── test_schemas.py
│   │   │   ├── reddit/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_registry.py
│   │   │   │   ├── scrape/
│   │   │   ├── tiktok/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_registry.py
│   │   │   │   ├── comments/
│   │   │   │   ├── scrape/
│   │   │   │   ├── trending/
│   │   │   │   ├── user_search/
│   │   │   ├── web/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── crawl/
│   │   │   ├── youtube/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_registry.py
│   │   │   │   ├── comments/
│   │   │   │   ├── scrape/
│   │   ├── config/
│   │   │   ├── test_embedding_settings.py
│   │   ├── connector_indexers/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_confluence_parallel.py
│   │   │   ├── test_content_extraction.py
│   │   │   ├── test_dropbox_parallel.py
│   │   │   ├── test_etl_credits.py
│   │   │   ├── test_google_drive_parallel.py
│   │   │   ├── test_linear_parallel.py
│   │   │   ├── test_local_folder_scan.py
│   │   │   ├── test_notion_parallel.py
│   │   │   ├── test_onedrive_parallel.py
│   │   ├── connectors/
│   │   │   ├── __init__.py
│   │   │   ├── test_dropbox_client.py
│   │   │   ├── test_dropbox_file_types.py
│   │   │   ├── test_dropbox_reauth.py
│   │   │   ├── test_google_drive_file_types.py
│   │   │   ├── test_onedrive_file_types.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── test_relax_revision_fks_migration.py
│   │   ├── e2e_fakes/
│   │   │   ├── test_drive_list_files.py
│   │   ├── etl_pipeline/
│   │   │   ├── conftest.py
│   │   │   ├── test_etl_pipeline_service.py
│   │   │   ├── test_picture_describer.py
│   │   │   ├── test_vision_llm.py
│   │   │   ├── cache/
│   │   │   │   ├── conftest.py
│   │   │   │   ├── test_eligibility.py
│   │   │   │   ├── test_eviction_policy.py
│   │   │   │   ├── test_parse_key.py
│   │   ├── event_bus/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_bus.py
│   │   │   ├── test_catalog.py
│   │   │   ├── test_document_entered_folder.py
│   │   │   ├── test_entered_folder_predicate.py
│   │   │   ├── test_event.py
│   │   ├── gateway/
│   │   │   ├── test_byo_long_poll_lifespan.py
│   │   │   ├── test_discord_adapter.py
│   │   │   ├── test_enqueue_received_sweep.py
│   │   │   ├── test_formatting.py
│   │   │   ├── test_hitl_filter.py
│   │   │   ├── test_inbox_worker.py
│   │   │   ├── test_pairing.py
│   │   │   ├── test_process_inbound_event_task.py
│   │   │   ├── test_slack_adapter.py
│   │   │   ├── test_webhook_routes.py
│   │   ├── google_unification/
│   │   │   ├── __init__.py
│   │   │   ├── test_composio_credentials.py
│   │   │   ├── test_connector_credential_acceptance.py
│   │   │   ├── test_schedule_checker_routing.py
│   │   ├── indexing_pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_chunk_reconciler.py
│   │   │   ├── test_connector_document.py
│   │   │   ├── test_create_placeholder_documents.py
│   │   │   ├── test_document_chunker.py
│   │   │   ├── test_document_hashing.py
│   │   │   ├── test_index_batch.py
│   │   │   ├── test_index_batch_parallel.py
│   │   │   ├── test_migrate_legacy_docs.py
│   │   │   ├── test_persist_scratch_index.py
│   │   │   ├── test_prepare_placeholder_dedup.py
│   │   │   ├── cache/
│   │   │   │   ├── conftest.py
│   │   │   │   ├── test_eligibility.py
│   │   │   │   ├── test_embedding_key.py
│   │   │   │   ├── test_serialization.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── test_b_filesystem_path_resolution.py
│   │   │   ├── test_b_filesystem_rm_rmdir_cloud.py
│   │   │   ├── test_b_filesystem_system_prompt.py
│   │   │   ├── test_dedup_hitl_tool_calls.py
│   │   │   ├── test_filesystem_backends.py
│   │   │   ├── test_kb_persistence_filesystem_parity.py
│   │   │   ├── test_kb_persistence_revisions.py
│   │   │   ├── test_kb_postgres_read.py
│   │   │   ├── test_knowledge_tree.py
│   │   │   ├── test_local_folder_backend.py
│   │   │   ├── test_multi_root_local_folder_backend.py
│   │   ├── notifications/
│   │   │   ├── api/
│   │   │   │   ├── test_transform.py
│   │   │   ├── service/
│   │   │   │   ├── test_metadata.py
│   │   │   │   ├── messages/
│   │   ├── observability/
│   │   │   ├── __init__.py
│   │   │   ├── test_helpers.py
│   │   │   ├── test_otel.py
│   │   │   ├── test_retriever_otel.py
│   │   ├── platforms/
│   │   │   ├── __init__.py
│   │   │   ├── amazon/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_flows.py
│   │   │   │   ├── test_locale.py
│   │   │   │   ├── test_parsers.py
│   │   │   │   ├── test_proxy.py
│   │   │   │   ├── test_skeleton.py
│   │   │   │   ├── fixtures/
│   │   │   ├── google_maps/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_parsers.py
│   │   │   │   ├── test_reviews.py
│   │   │   │   ├── test_search.py
│   │   │   │   ├── test_skeleton.py
│   │   │   ├── google_search/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_browser_loop.py
│   │   │   │   ├── test_captcha.py
│   │   │   │   ├── test_fetch_concurrency.py
│   │   │   │   ├── test_fetch_pool.py
│   │   │   │   ├── test_pool_store.py
│   │   │   │   ├── test_skeleton.py
│   │   │   ├── instagram/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_budget.py
│   │   │   │   ├── test_discovery.py
│   │   │   │   ├── test_fetch_resilience.py
│   │   │   │   ├── test_parsers.py
│   │   │   │   ├── test_skeleton.py
│   │   │   ├── reddit/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_fetch_resilience.py
│   │   │   │   ├── test_parsers.py
│   │   │   │   ├── test_search_budget.py
│   │   │   │   ├── test_skeleton.py
│   │   │   │   ├── fixtures/
│   │   │   ├── tiktok/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_comments.py
│   │   │   │   ├── test_fetch_resilience.py
│   │   │   │   ├── test_hydration.py
│   │   │   │   ├── test_input.py
│   │   │   │   ├── test_item_list.py
│   │   │   │   ├── test_listing_retry.py
│   │   │   │   ├── test_orchestrator.py
│   │   │   │   ├── test_parsers.py
│   │   │   │   ├── test_scopes.py
│   │   │   │   ├── test_target_resolver.py
│   │   │   │   ├── test_trending.py
│   │   │   │   ├── test_user_search.py
│   │   │   ├── youtube/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_fetch_resilience.py
│   │   │   │   ├── test_parsers.py
│   │   │   │   ├── test_subtitles_retry.py
│   │   ├── podcasts/
│   │   │   ├── conftest.py
│   │   │   ├── test_api_schemas.py
│   │   │   ├── test_renderer.py
│   │   │   ├── test_resolution.py
│   │   │   ├── test_spec.py
│   │   │   ├── test_structured.py
│   │   │   ├── test_voice_catalog.py
│   │   ├── proprietary/
│   │   │   ├── __init__.py
│   │   │   ├── web_crawler/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_captcha.py
│   │   │   │   ├── test_connector.py
│   │   │   │   ├── test_connector_links.py
│   │   │   │   ├── test_site_crawler.py
│   │   │   │   ├── test_stealth.py
│   │   │   │   ├── test_url_policy.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── test_image_gen_quota.py
│   │   │   ├── test_llm_setup_status.py
│   │   │   ├── test_regenerate_from_message_id.py
│   │   │   ├── test_revert_turn_route.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── test_agent_billing_resolver.py
│   │   │   ├── test_auto_model_pin_service.py
│   │   │   ├── test_auto_pin_image_aware.py
│   │   │   ├── test_billable_call.py
│   │   │   ├── test_docling_image_support.py
│   │   │   ├── test_folder_hierarchy.py
│   │   │   ├── test_image_gen_api_base_defense.py
│   │   │   ├── test_llm_router_pool_filter.py
│   │   │   ├── test_memory_service.py
│   │   │   ├── test_model_connections.py
│   │   │   ├── test_openrouter_integration_service.py
│   │   │   ├── test_openrouter_legacy_config.py
│   │   │   ├── test_or_health_enrichment.py
│   │   │   ├── test_pricing_registration.py
│   │   │   ├── test_provider_capabilities.py
│   │   │   ├── test_quality_score.py
│   │   │   ├── test_quota_checked_vision_llm.py
│   │   │   ├── test_requesty_model_normalizer.py
│   │   │   ├── test_revert_filesystem_tools.py
│   │   │   ├── streaming/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_emitter.py
│   │   │   │   ├── test_emitter_registry.py
│   │   │   │   ├── test_interrupt_correlation.py
│   │   │   │   ├── test_interrupt_events.py
│   │   │   │   ├── test_service_emitter_propagation.py
│   │   │   │   ├── test_sse_envelope.py
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── test_celery_async_runner.py
│   │   │   ├── test_stream_new_chat_image_safety_net.py
│   │   │   ├── test_video_presentation_billing.py
│   │   │   ├── celery_tasks/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_schedule_checker_task.py
│   │   │   ├── chat/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_content_builder.py
│   │   │   │   ├── test_extract_chunk_parts.py
│   │   │   │   ├── test_llm_history_normalizer.py
│   │   │   │   ├── test_message_parts_normalizer.py
│   │   │   │   ├── test_thinking_step_id_uniqueness.py
│   │   │   │   ├── test_tool_input_streaming.py
│   │   │   │   ├── streaming/
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── test_async_retry.py
│   │   │   ├── test_blocknote_to_markdown.py
│   │   │   ├── test_captcha_config.py
│   │   │   ├── test_content_utils.py
│   │   │   ├── test_crawl_classifier.py
│   │   │   ├── test_file_extensions.py
│   │   │   ├── test_oauth_security.py
│   │   │   ├── test_validators.py
│   │   │   ├── captcha/
│   │   │   │   ├── test_solvers.py
│   │   │   ├── crawl/
│   │   │   │   ├── test_contacts.py
│   │   │   ├── proxy/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_custom_provider.py
│   │   │   │   ├── test_dataimpulse_provider.py
│   │   │   │   ├── test_registry.py
│   │   │   │   ├── test_rotation.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── helpers.py
```

### surfsense_web

```
surfsense_web/
├── .cursorrules
├── .dockerignore
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
├── LICENSE
├── biome.json
├── components.json
├── drizzle.config.ts
├── eslint.config.mjs
├── instrumentation-client.ts
├── instrumentation.ts
├── mdx-components.tsx
├── next-env.d.ts
├── next.config.ts
├── package.json
├── playwright.config.ts
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── postcss.config.mjs
├── proxy.ts
├── source.config.ts
├── svgr.d.ts
├── tailwind.config.js
├── tsc_out.txt
├── tsconfig.json
├── app/
│   ├── apple-icon.png
│   ├── error.tsx
│   ├── favicon.ico
│   ├── global-error.tsx
│   ├── globals.css
│   ├── icon.png
│   ├── layout.config.tsx
│   ├── layout.tsx
│   ├── not-found.tsx
│   ├── robots.ts
│   ├── sitemap.ts
│   ├── (home)/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── [slug]/
│   │   │   ├── page.tsx
│   │   ├── announcements/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   ├── blog/
│   │   │   ├── blog-magazine.tsx
│   │   │   ├── loading.tsx
│   │   │   ├── page.tsx
│   │   │   ├── [slug]/
│   │   │   │   ├── loading.tsx
│   │   │   │   ├── page.tsx
│   │   ├── changelog/
│   │   │   ├── loading.tsx
│   │   │   ├── page.tsx
│   │   ├── connectors/
│   │   │   ├── page.tsx
│   │   ├── contact/
│   │   │   ├── page.tsx
│   │   ├── external-mcp-connectors/
│   │   │   ├── page.tsx
│   │   ├── free/
│   │   │   ├── layout.tsx
│   │   │   ├── loading.tsx
│   │   │   ├── page.tsx
│   │   │   ├── [model_slug]/
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── loading.tsx
│   │   │   │   ├── page.tsx
│   │   ├── login/
│   │   │   ├── AmbientBackground.tsx
│   │   │   ├── GoogleLoginButton.tsx
│   │   │   ├── LocalLoginForm.tsx
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   ├── mcp-server/
│   │   │   ├── page.tsx
│   │   ├── pricing/
│   │   │   ├── page.tsx
│   │   ├── privacy/
│   │   │   ├── page.tsx
│   │   ├── register/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   ├── terms/
│   │   │   ├── page.tsx
│   ├── api/
│   │   ├── contact/
│   │   │   ├── route.ts
│   │   ├── search/
│   │   │   ├── route.ts
│   │   ├── v1/
│   │   │   ├── [...path]/
│   │   │   │   ├── route.ts
│   │   ├── zero/
│   │   │   ├── mutate/
│   │   │   │   ├── route.ts
│   │   │   ├── query/
│   │   │   │   ├── route.ts
│   ├── auth/
│   │   ├── [...path]/
│   │   │   ├── route.ts
│   │   ├── callback/
│   │   │   ├── loading.tsx
│   ├── dashboard/
│   │   ├── dashboard-shell.tsx
│   │   ├── error.tsx
│   │   ├── layout.tsx
│   │   ├── loading.tsx
│   │   ├── page.tsx
│   │   ├── [workspace_id]/
│   │   │   ├── client-layout.tsx
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── artifacts/
│   │   │   │   ├── page.tsx
│   │   │   ├── automations/
│   │   │   │   ├── automations-content.tsx
│   │   │   │   ├── page.tsx
│   │   │   │   ├── [automation_id]/
│   │   │   │   ├── components/
│   │   │   │   ├── hooks/
│   │   │   │   ├── new/
│   │   │   ├── buy-more/
│   │   │   │   ├── page.tsx
│   │   │   ├── buy-pages/
│   │   │   │   ├── page.tsx
│   │   │   ├── buy-tokens/
│   │   │   │   ├── page.tsx
│   │   │   ├── chats/
│   │   │   │   ├── page.tsx
│   │   │   ├── connectors/
│   │   │   │   ├── callback/
│   │   │   ├── earn-credits/
│   │   │   │   ├── page.tsx
│   │   │   ├── logs/
│   │   │   │   ├── loading.tsx
│   │   │   │   ├── (manage)/
│   │   │   ├── more-pages/
│   │   │   │   ├── page.tsx
│   │   │   ├── new-chat/
│   │   │   │   ├── loading.tsx
│   │   │   │   ├── [[...chat_id]]/
│   │   │   ├── onboard/
│   │   │   │   ├── page.tsx
│   │   │   ├── playground/
│   │   │   │   ├── layout-shell.tsx
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx
│   │   │   │   ├── [platform]/
│   │   │   │   ├── api-keys/
│   │   │   │   ├── components/
│   │   │   │   ├── runs/
│   │   │   ├── purchase-cancel/
│   │   │   │   ├── page.tsx
│   │   │   ├── purchase-success/
│   │   │   │   ├── page.tsx
│   │   │   ├── team/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── team-content.tsx
│   │   │   ├── user-settings/
│   │   │   │   ├── layout-shell.tsx
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx
│   │   │   │   ├── agent-permissions/
│   │   │   │   ├── api-key/
│   │   │   │   ├── appearance/
│   │   │   │   ├── community-prompts/
│   │   │   │   ├── components/
│   │   │   │   ├── desktop/
│   │   │   │   ├── hotkeys/
│   │   │   │   ├── messaging-channels/
│   │   │   │   ├── profile/
│   │   │   │   ├── prompts/
│   │   │   │   ├── purchases/
│   │   │   ├── workspace-settings/
│   │   │   │   ├── layout-shell.tsx
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx
│   │   │   │   ├── general/
│   │   │   │   ├── models/
│   │   │   │   ├── prompts/
│   │   │   │   ├── public-links/
│   │   │   │   ├── team-roles/
│   ├── db/
│   │   ├── index.ts
│   │   ├── schema.ts
│   ├── desktop/
│   │   ├── login/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   ├── permissions/
│   │   │   ├── page.tsx
│   ├── docs/
│   │   ├── layout.tsx
│   │   ├── sidebar-separator.tsx
│   │   ├── [[...slug]]/
│   │   │   ├── loading.tsx
│   │   │   ├── page.tsx
│   ├── invite/
│   │   ├── [invite_code]/
│   │   │   ├── page.tsx
│   ├── public/
│   │   ├── [token]/
│   │   │   ├── page.tsx
│   ├── verify-token/
│   │   ├── route.ts
├── atoms/
│   ├── agent/
│   │   ├── action-log-dialog.atom.ts
│   │   ├── agent-flags-query.atom.ts
│   ├── agent-tools/
│   │   ├── agent-tools.atoms.ts
│   ├── auth/
│   │   ├── auth-mutation.atoms.ts
│   ├── automations/
│   │   ├── automations-mutation.atoms.ts
│   │   ├── automations-query.atoms.ts
│   ├── chat/
│   │   ├── chat-session-state.atom.ts
│   │   ├── current-thread.atom.ts
│   │   ├── mentioned-documents.atom.ts
│   │   ├── pending-user-images.atom.ts
│   │   ├── plan-state.atom.ts
│   │   ├── premium-alert.atom.ts
│   │   ├── report-panel.atom.ts
│   │   ├── show-timestamps.atom.ts
│   ├── chat-comments/
│   │   ├── comments-mutation.atoms.ts
│   ├── citation/
│   │   ├── citation-panel.atom.ts
│   ├── connector-dialog/
│   │   ├── connector-dialog.atoms.ts
│   ├── connectors/
│   │   ├── connector-mutation.atoms.ts
│   │   ├── connector-query.atoms.ts
│   │   ├── ui.atoms.ts
│   ├── documents/
│   │   ├── document-mutation.atoms.ts
│   │   ├── folder.atoms.ts
│   │   ├── ui.atoms.ts
│   ├── editor/
│   │   ├── editor-panel.atom.ts
│   ├── folder-sync/
│   │   ├── folder-sync.atoms.ts
│   ├── inbox/
│   │   ├── status-inbox.atom.ts
│   ├── invites/
│   │   ├── invites-mutation.atoms.ts
│   │   ├── invites-query.atoms.ts
│   ├── layout/
│   │   ├── dialogs.atom.ts
│   │   ├── right-panel.atom.ts
│   ├── logs/
│   │   ├── log-mutation.atoms.ts
│   ├── members/
│   │   ├── members-mutation.atoms.ts
│   │   ├── members-query.atoms.ts
│   ├── model-connections/
│   │   ├── model-connections-mutation.atoms.ts
│   │   ├── model-connections-query.atoms.ts
│   ├── permissions/
│   │   ├── permissions-query.atoms.ts
│   ├── prompts/
│   │   ├── prompts-mutation.atoms.ts
│   │   ├── prompts-query.atoms.ts
│   ├── public-chat-snapshots/
│   │   ├── public-chat-snapshots-mutation.atoms.ts
│   │   ├── public-chat-snapshots-query.atoms.ts
│   ├── roles/
│   │   ├── roles-mutation.atoms.ts
│   ├── tabs/
│   │   ├── migrate-tabs.test.ts
│   │   ├── migrate-tabs.ts
│   │   ├── tabs.atom.ts
│   ├── ui/
│   │   ├── loading.atoms.ts
│   ├── user/
│   │   ├── user-mutation.atoms.ts
│   │   ├── user-query.atoms.ts
│   ├── workspaces/
│   │   ├── workspace-mutation.atoms.ts
│   │   ├── workspace-query.atoms.ts
├── blog/
│   ├── content/
│   │   ├── agentic-rag-vs-long-context-llms-benchmark.mdx
│   │   ├── no-login-ai-privacy-reality-check.mdx
├── changelog/
│   ├── content/
│   │   ├── 2025-12-24.mdx
│   │   ├── 2026-01-08.mdx
│   │   ├── 2026-01-26.mdx
│   │   ├── 2026-02-09.mdx
│   │   ├── 2026-03-31.mdx
│   │   ├── 2026-04-08.mdx
│   │   ├── 2026-04-16.mdx
│   │   ├── 2026-04-21.mdx
│   │   ├── 2026-05-03.mdx
│   │   ├── 2026-05-04.mdx
│   │   ├── 2026-05-05.mdx
│   │   ├── 2026-05-06.mdx
│   │   ├── 2026-05-20.mdx
│   │   ├── 2026-05-21.mdx
│   │   ├── 2026-05-31.mdx
│   │   ├── 2026-07-05.mdx
├── components/
│   ├── LanguageSwitcher.tsx
│   ├── Logo.tsx
│   ├── UserDropdown.tsx
│   ├── container.tsx
│   ├── document-viewer.tsx
│   ├── inference-params-editor.tsx
│   ├── json-metadata-viewer.tsx
│   ├── json-view.tsx
│   ├── markdown-viewer.tsx
│   ├── onboarding-tour.tsx
│   ├── platform-gate.tsx
│   ├── pricing.tsx
│   ├── workspace-form.tsx
│   ├── ads/
│   │   ├── ad-unit.tsx
│   │   ├── adsense-config.ts
│   │   ├── adsense-script.tsx
│   ├── agent-action-log/
│   │   ├── action-log-button.tsx
│   │   ├── action-log-dialog.tsx
│   │   ├── action-log-item.tsx
│   ├── announcements/
│   │   ├── AnnouncementCard.tsx
│   │   ├── AnnouncementSpotlight.tsx
│   │   ├── AnnouncementToastProvider.tsx
│   │   ├── AnnouncementsDialog.tsx
│   │   ├── AnnouncementsEmptyState.tsx
│   ├── assistant-ui/
│   │   ├── assistant-message.tsx
│   │   ├── chat-session-status.tsx
│   │   ├── chat-viewport.tsx
│   │   ├── citation-metadata-context.tsx
│   │   ├── connector-popup.tsx
│   │   ├── document-upload-popup.tsx
│   │   ├── edit-composer.tsx
│   │   ├── edit-message-dialog.tsx
│   │   ├── image.tsx
│   │   ├── inline-citation.tsx
│   │   ├── inline-mention-editor.tsx
│   │   ├── markdown-code-block.tsx
│   │   ├── markdown-text.tsx
│   │   ├── mention-chip.tsx
│   │   ├── mermaid-diagram.tsx
│   │   ├── message-timestamp.tsx
│   │   ├── nested-scroll.tsx
│   │   ├── reasoning-message-part.tsx
│   │   ├── revert-turn-button.tsx
│   │   ├── step-separator.tsx
│   │   ├── thread.tsx
│   │   ├── token-usage-context.tsx
│   │   ├── tooltip-icon-button.tsx
│   │   ├── user-message.tsx
│   │   ├── connector-popup/
│   │   │   ├── index.ts
│   │   │   ├── components/
│   │   │   │   ├── connector-card.tsx
│   │   │   │   ├── connector-dialog-header.tsx
│   │   │   │   ├── connector-status-badge.tsx
│   │   │   │   ├── connector-warning-banner.tsx
│   │   │   │   ├── date-range-selector.tsx
│   │   │   │   ├── periodic-sync-config.tsx
│   │   │   │   ├── vision-llm-config.tsx
│   │   │   ├── config/
│   │   │   │   ├── connector-status-config.example.json
│   │   │   │   ├── connector-status-config.json
│   │   │   │   ├── connector-status-config.ts
│   │   │   ├── connect-forms/
│   │   │   │   ├── connector-benefits.ts
│   │   │   │   ├── index.tsx
│   │   │   │   ├── components/
│   │   │   ├── connector-configs/
│   │   │   │   ├── index.tsx
│   │   │   │   ├── components/
│   │   │   │   ├── views/
│   │   │   ├── constants/
│   │   │   │   ├── connector-constants.ts
│   │   │   │   ├── connector-popup.schemas.ts
│   │   │   ├── hooks/
│   │   │   │   ├── use-connector-dialog.ts
│   │   │   │   ├── use-connector-status.ts
│   │   │   │   ├── use-indexing-connectors.ts
│   │   │   ├── tabs/
│   │   │   │   ├── active-connectors-tab.tsx
│   │   │   │   ├── all-connectors-tab.tsx
│   │   │   ├── utils/
│   │   │   │   ├── connector-document-mapping.ts
│   │   │   │   ├── mcp-config-validator.ts
│   │   │   ├── views/
│   │   │   │   ├── connector-accounts-list-view.tsx
│   │   │   │   ├── youtube-crawler-view.tsx
│   ├── auth/
│   │   ├── sign-in-button.tsx
│   ├── chat/
│   │   ├── active-chat-stream-runner.tsx
│   ├── chat-comments/
│   │   ├── comment-composer/
│   │   │   ├── comment-composer.tsx
│   │   │   ├── types.ts
│   │   ├── comment-item/
│   │   │   ├── comment-actions.tsx
│   │   │   ├── comment-item.tsx
│   │   │   ├── types.ts
│   │   ├── comment-panel/
│   │   │   ├── comment-panel.tsx
│   │   │   ├── types.ts
│   │   ├── comment-panel-container/
│   │   │   ├── comment-panel-container.tsx
│   │   │   ├── types.ts
│   │   │   ├── utils.ts
│   │   ├── comment-sheet/
│   │   │   ├── comment-sheet.tsx
│   │   │   ├── types.ts
│   │   ├── comment-thread/
│   │   │   ├── comment-thread.tsx
│   │   │   ├── types.ts
│   │   ├── member-mention-picker/
│   │   │   ├── member-mention-item.tsx
│   │   │   ├── member-mention-picker.tsx
│   │   │   ├── types.ts
│   ├── citation-panel/
│   │   ├── citation-panel.tsx
│   ├── citations/
│   │   ├── citation-renderer.tsx
│   ├── connectors/
│   │   ├── drive-folder-tree.tsx
│   │   ├── google-drive-folder-tree.tsx
│   ├── connectors-marketing/
│   │   ├── agent-transcript.tsx
│   │   ├── api-mcp-tabs.tsx
│   │   ├── connector-faq.tsx
│   │   ├── connector-page.tsx
│   │   ├── reveal.tsx
│   ├── contact/
│   │   ├── contact-form.tsx
│   ├── desktop/
│   │   ├── desktop-update-toast.tsx
│   │   ├── shortcut-recorder.tsx
│   ├── documents/
│   │   ├── CreateFolderDialog.tsx
│   │   ├── DocumentNode.tsx
│   │   ├── DocumentTypeIcon.tsx
│   │   ├── DocumentsFilters.tsx
│   │   ├── FolderNode.tsx
│   │   ├── FolderPickerDialog.tsx
│   │   ├── FolderTreeView.tsx
│   │   ├── download-original-button.tsx
│   │   ├── version-history.tsx
│   ├── editor/
│   │   ├── editor-save-context.tsx
│   │   ├── plate-editor.tsx
│   │   ├── plate-error-boundary.tsx
│   │   ├── presets.ts
│   │   ├── source-code-editor.tsx
│   │   ├── transforms.ts
│   │   ├── plugins/
│   │   │   ├── autoformat-kit.tsx
│   │   │   ├── basic-blocks-kit.tsx
│   │   │   ├── basic-marks-kit.tsx
│   │   │   ├── basic-nodes-kit.tsx
│   │   │   ├── callout-kit.tsx
│   │   │   ├── citation-kit.tsx
│   │   │   ├── code-block-kit.tsx
│   │   │   ├── dnd-kit.tsx
│   │   │   ├── fixed-toolbar-kit.tsx
│   │   │   ├── floating-toolbar-kit.tsx
│   │   │   ├── indent-kit.tsx
│   │   │   ├── link-kit.tsx
│   │   │   ├── list-kit.tsx
│   │   │   ├── math-kit.tsx
│   │   │   ├── selection-kit.tsx
│   │   │   ├── slash-command-kit.tsx
│   │   │   ├── table-kit.tsx
│   │   │   ├── toggle-kit.tsx
│   │   ├── utils/
│   │   │   ├── escape-mdx.ts
│   │   │   ├── safe-deserialize.ts
│   ├── editor-panel/
│   │   ├── editor-panel.tsx
│   │   ├── memory.ts
│   ├── free-chat/
│   │   ├── anonymous-chat.tsx
│   │   ├── free-chat-page.tsx
│   │   ├── free-composer.tsx
│   │   ├── free-model-selector.tsx
│   │   ├── free-right-panel.tsx
│   │   ├── free-thread.tsx
│   │   ├── quota-bar.tsx
│   │   ├── quota-warning-banner.tsx
│   │   ├── remove-ads-banner.tsx
│   ├── homepage/
│   │   ├── auth-redirect.tsx
│   │   ├── community-strip.tsx
│   │   ├── compare-table.tsx
│   │   ├── connector-grid.tsx
│   │   ├── flow-line.tsx
│   │   ├── footer-new.tsx
│   │   ├── github-stars-badge.tsx
│   │   ├── global-announcement.tsx
│   │   ├── hero-chat-demo.tsx
│   │   ├── hero-section.tsx
│   │   ├── home-faq.tsx
│   │   ├── how-it-works.tsx
│   │   ├── logo-cloud.tsx
│   │   ├── navbar.tsx
│   │   ├── persona-paths.tsx
│   │   ├── social-proof.tsx
│   │   ├── use-case-art.tsx
│   │   ├── use-cases-grid.tsx
│   │   ├── use-cases.tsx
│   ├── icons/
│   │   ├── providers/
│   │   │   ├── ai21.svg
│   │   │   ├── anthropic.svg
│   │   │   ├── anyscale.svg
│   │   │   ├── azure.svg
│   │   │   ├── bedrock.svg
│   │   │   ├── cerebras.svg
│   │   │   ├── claude.svg
│   │   │   ├── cohere.svg
│   │   │   ├── cometapi.svg
│   │   │   ├── dbrx.svg
│   │   │   ├── deepinfra.svg
│   │   │   ├── deepseek.svg
│   │   │   ├── fireworksai.svg
│   │   │   ├── gemini.svg
│   │   │   ├── github.svg
│   │   │   ├── groq.svg
│   │   │   ├── huggingface.svg
│   │   │   ├── index.ts
│   │   │   ├── lm-studio.svg
│   │   │   ├── minimax.svg
│   ├── layout/
│   │   ├── index.ts
│   │   ├── hooks/
│   │   │   ├── SidebarContext.tsx
│   │   │   ├── index.ts
│   │   │   ├── useSidebarResize.ts
│   │   │   ├── useSidebarState.ts
│   │   ├── providers/
│   │   │   ├── FreeLayoutDataProvider.tsx
│   │   │   ├── LayoutDataProvider.tsx
│   │   │   ├── index.ts
│   │   ├── types/
│   │   │   ├── layout.types.ts
│   │   ├── ui/
│   │   │   ├── RoutedSectionShell.tsx
│   │   │   ├── index.ts
│   │   │   ├── dialogs/
│   │   │   │   ├── CreateWorkspaceDialog.tsx
│   │   │   │   ├── index.ts
│   │   │   ├── header/
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── index.ts
│   │   │   ├── icon-rail/
│   │   │   │   ├── IconRail.tsx
│   │   │   │   ├── NavIcon.tsx
│   │   │   │   ├── WorkspaceAvatar.tsx
│   │   │   │   ├── index.ts
│   │   │   ├── playground/
│   │   │   │   ├── PlaygroundSidebar.tsx
│   │   │   ├── right-panel/
│   │   │   │   ├── RightPanel.tsx
│   │   │   ├── shell/
│   │   │   │   ├── LayoutShell.tsx
│   │   │   │   ├── WorkspacePanel.tsx
│   │   │   │   ├── index.ts
│   │   │   ├── sidebar/
│   │   │   │   ├── AllChatsSidebar.tsx
│   │   │   │   ├── ChatListItem.tsx
│   │   │   │   ├── CreditBalanceDisplay.tsx
│   │   │   │   ├── DesktopLocalTabContent.tsx
│   │   │   │   ├── DocumentsSidebar.tsx
│   │   │   │   ├── LocalFilesystemBrowser.tsx
│   │   │   │   ├── MobileSidebar.tsx
│   │   │   │   ├── NavSection.tsx
│   │   │   │   ├── NotificationsDropdown.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── SidebarButton.tsx
│   │   │   │   ├── SidebarCollapseButton.tsx
│   │   │   │   ├── SidebarHeader.tsx
│   │   │   │   ├── SidebarListItem.tsx
│   │   │   │   ├── SidebarSection.tsx
│   │   │   │   ├── SidebarUserProfile.tsx
│   │   │   │   ├── index.ts
│   │   │   ├── tabs/
│   │   │   │   ├── DocumentTabContent.tsx
│   │   │   │   ├── TabBar.tsx
│   ├── marketing/
│   │   ├── section.tsx
│   ├── mcp/
│   │   ├── agent-setup-tabs.tsx
│   │   ├── connect-agent-dialog.tsx
│   ├── new-chat/
│   │   ├── chat-example-prompts.tsx
│   │   ├── chat-header.tsx
│   │   ├── chat-share-button.tsx
│   │   ├── composer-suggestion-popup.tsx
│   │   ├── document-mention-picker.tsx
│   │   ├── image-model-selector.tsx
│   │   ├── model-selector.tsx
│   │   ├── prompt-picker.tsx
│   │   ├── use-composer-suggestion-navigator.ts
│   ├── pricing/
│   │   ├── pricing-section.tsx
│   ├── prompt-kit/
│   │   ├── chain-of-thought.tsx
│   │   ├── loader.tsx
│   ├── providers/
│   │   ├── AuthCutoverPurge.tsx
│   │   ├── GlobalLoadingProvider.tsx
│   │   ├── I18nProvider.tsx
│   │   ├── PostHogIdentify.tsx
│   │   ├── PostHogProvider.tsx
│   │   ├── PostHogReferral.tsx
│   │   ├── ZeroProvider.tsx
│   │   ├── runtime-config.server.tsx
│   │   ├── runtime-config.tsx
│   ├── public-chat/
│   │   ├── public-chat-footer.tsx
│   │   ├── public-chat-not-found.tsx
│   │   ├── public-chat-view.tsx
│   │   ├── public-thread.tsx
│   ├── public-chat-snapshots/
│   │   ├── public-chat-snapshot-row.tsx
│   │   ├── public-chat-snapshots-empty-state.tsx
│   │   ├── public-chat-snapshots-list.tsx
│   │   ├── public-chat-snapshots-manager.tsx
│   ├── report-panel/
│   │   ├── pdf-viewer.tsx
│   │   ├── report-panel.tsx
│   ├── seo/
│   │   ├── breadcrumb-nav.tsx
│   │   ├── json-ld.tsx
│   ├── settings/
│   │   ├── auto-reload-settings.tsx
│   │   ├── buy-credits-content.tsx
│   │   ├── earn-credits-content.tsx
│   │   ├── general-settings-manager.tsx
│   │   ├── model-connections-settings.tsx
│   │   ├── prompt-config-manager.tsx
│   │   ├── roles-manager.tsx
│   │   ├── workspace-api-access-control.tsx
│   │   ├── model-connections/
│   │   │   ├── azure-connect-form.tsx
│   │   │   ├── bedrock-connect-form.tsx
│   │   │   ├── connect-fields.tsx
│   │   │   ├── connection-card.tsx
│   │   │   ├── connection-settings-dialog.tsx
│   │   │   ├── default-connect-form.tsx
│   │   │   ├── model-provider-connections-panel.tsx
│   │   │   ├── model-utils.ts
│   │   │   ├── models-selection-panel.tsx
│   │   │   ├── provider-connect-dialog.tsx
│   │   │   ├── provider-metadata.tsx
│   │   │   ├── vertex-connect-form.tsx
│   ├── shared/
│   │   ├── ExportMenuItems.tsx
│   ├── sources/
│   │   ├── DocumentUploadTab.tsx
│   │   ├── FolderWatchDialog.tsx
│   │   ├── GridPattern.tsx
│   ├── theme/
│   │   ├── theme-provider.tsx
│   │   ├── theme-toggle.tsx
│   ├── tool-ui/
│   │   ├── audio.tsx
│   │   ├── generate-image.tsx
│   │   ├── generate-report.tsx
│   │   ├── generate-resume.tsx
│   │   ├── index.ts
│   │   ├── sandbox-execute.tsx
│   │   ├── user-memory.tsx
│   │   ├── write-todos.tsx
│   │   ├── automation/
│   │   │   ├── automation-draft-preview.tsx
│   │   │   ├── create-automation.tsx
│   │   │   ├── index.ts
│   │   ├── citation/
│   │   │   ├── _adapter.tsx
│   │   │   ├── citation-hover-popover.tsx
│   │   │   ├── citation.tsx
│   │   │   ├── index.ts
│   │   │   ├── schema.ts
│   │   │   ├── type-icons.ts
│   │   ├── confluence/
│   │   │   ├── create-confluence-page.tsx
│   │   │   ├── delete-confluence-page.tsx
│   │   │   ├── index.ts
│   │   │   ├── update-confluence-page.tsx
│   │   ├── dropbox/
│   │   │   ├── create-file.tsx
│   │   │   ├── index.ts
│   │   │   ├── trash-file.tsx
│   │   ├── gmail/
│   │   │   ├── create-draft.tsx
│   │   │   ├── index.ts
│   │   │   ├── send-email.tsx
│   │   │   ├── trash-email.tsx
│   │   │   ├── update-draft.tsx
│   │   ├── google-calendar/
│   │   │   ├── create-event.tsx
│   │   │   ├── delete-event.tsx
│   │   │   ├── index.ts
│   │   │   ├── update-event.tsx
│   │   ├── google-drive/
│   │   │   ├── create-file.tsx
│   │   │   ├── index.ts
│   │   │   ├── trash-file.tsx
│   │   ├── image/
│   │   │   ├── index.tsx
│   │   ├── jira/
│   │   │   ├── create-jira-issue.tsx
│   │   │   ├── delete-jira-issue.tsx
│   │   │   ├── index.ts
│   │   │   ├── update-jira-issue.tsx
│   │   ├── linear/
│   │   │   ├── create-linear-issue.tsx
│   │   │   ├── delete-linear-issue.tsx
│   │   │   ├── index.ts
│   │   │   ├── update-linear-issue.tsx
│   │   ├── notion/
│   │   │   ├── create-notion-page.tsx
│   │   │   ├── delete-notion-page.tsx
│   │   │   ├── index.ts
│   │   │   ├── update-notion-page.tsx
│   │   ├── onedrive/
│   │   │   ├── create-file.tsx
│   │   │   ├── index.ts
│   │   │   ├── trash-file.tsx
│   │   ├── plan/
│   │   │   ├── index.tsx
│   │   │   ├── plan.tsx
│   │   │   ├── schema.ts
│   │   ├── podcast/
│   │   │   ├── brief-review.tsx
│   │   │   ├── generate-podcast.tsx
│   │   │   ├── index.ts
│   │   │   ├── player.tsx
│   │   │   ├── schema.ts
│   │   │   ├── voice-preview-button.tsx
│   │   ├── shared/
│   │   │   ├── schema.ts
│   │   │   ├── media/
│   │   │   │   ├── index.ts
│   │   │   │   ├── safe-navigation.ts
│   │   │   │   ├── sanitize-href.ts
│   │   ├── video-presentation/
│   │   │   ├── combined-player.tsx
│   │   │   ├── errors.ts
│   │   │   ├── generate-video-presentation.tsx
│   │   │   ├── index.ts
│   ├── ui/
│   │   ├── accordion.tsx
│   │   ├── alert-dialog.tsx
│   │   ├── alert.tsx
│   │   ├── animated-tabs.tsx
│   │   ├── avatar.tsx
│   │   ├── badge.tsx
│   │   ├── bento-grid.tsx
│   │   ├── block-draggable.tsx
│   │   ├── block-list.tsx
│   │   ├── block-selection.tsx
│   │   ├── blockquote-node.tsx
│   │   ├── button.tsx
│   │   ├── calendar.tsx
│   │   ├── callout-node.tsx
│   │   ├── card.tsx
│   │   ├── changelog-timeline.tsx
│   │   ├── checkbox.tsx
│   │   ├── code-block-node.tsx
│   │   ├── code-node.tsx
│   │   ├── collapsible.tsx
│   │   ├── command.tsx
│   │   ├── context-menu.tsx
│   │   ├── dialog.tsx
│   │   ├── drawer.tsx
│   │   ├── dropdown-menu.tsx
│   │   ├── editor.tsx
│   │   ├── empty.tsx
│   │   ├── equation-node.tsx
│   │   ├── expanded-gif-overlay.tsx
│   │   ├── fixed-toolbar-buttons.tsx
│   │   ├── fixed-toolbar.tsx
│   │   ├── floating-toolbar-buttons.tsx
│   │   ├── floating-toolbar.tsx
│   │   ├── form.tsx
│   │   ├── heading-node.tsx
│   │   ├── hero-carousel.tsx
│   │   ├── highlight-node.tsx
│   │   ├── hr-node.tsx
│   │   ├── inline-combobox.tsx
│   │   ├── input.tsx
│   │   ├── insert-toolbar-button.tsx
│   │   ├── label.tsx
│   │   ├── link-node.tsx
│   │   ├── link-toolbar-button.tsx
│   │   ├── link-toolbar.tsx
│   │   ├── mark-toolbar-button.tsx
│   │   ├── mode-toolbar-button.tsx
│   │   ├── pagination.tsx
│   │   ├── paragraph-node.tsx
│   │   ├── popover.tsx
│   │   ├── progress.tsx
│   │   ├── radio-group.tsx
│   │   ├── resize-handle.tsx
│   │   ├── scroll-area.tsx
│   │   ├── select.tsx
│   │   ├── separator.tsx
│   │   ├── sheet.tsx
│   │   ├── shortcut-kbd.tsx
│   │   ├── sidebar.tsx
│   │   ├── skeleton.tsx
│   │   ├── slash-node.tsx
│   │   ├── slider.tsx
│   │   ├── sonner.tsx
│   │   ├── spinner.tsx
│   │   ├── spotlight.tsx
│   │   ├── switch.tsx
│   │   ├── table-icons.tsx
│   │   ├── table-node.tsx
│   │   ├── table.tsx
│   │   ├── tabs.tsx
│   │   ├── textarea.tsx
│   │   ├── tilt.tsx
│   │   ├── toggle-group.tsx
│   │   ├── toggle-node.tsx
│   │   ├── toggle.tsx
│   │   ├── toolbar.tsx
│   │   ├── tooltip.tsx
│   │   ├── turn-into-toolbar-button.tsx
├── content/
│   ├── docs/
│   │   ├── code-of-conduct.mdx
│   │   ├── index.mdx
│   │   ├── installation.mdx
│   │   ├── manual-installation.mdx
│   │   ├── meta.json
│   │   ├── observability.mdx
│   │   ├── testing.mdx
│   │   ├── connectors/
│   │   │   ├── index.mdx
│   │   │   ├── meta.json
│   │   │   ├── deprecated/
│   │   │   │   ├── baidu-search.mdx
│   │   │   │   ├── discord.mdx
│   │   │   │   ├── elasticsearch.mdx
│   │   │   │   ├── luma.mdx
│   │   │   │   ├── meta.json
│   │   │   │   ├── microsoft-teams.mdx
│   │   │   │   ├── web-crawler.mdx
│   │   │   ├── external/
│   │   │   │   ├── airtable.mdx
│   │   │   │   ├── bookstack.mdx
│   │   │   │   ├── circleback.mdx
│   │   │   │   ├── dropbox.mdx
│   │   │   │   ├── github.mdx
│   │   │   │   ├── google.mdx
│   │   │   │   ├── index.mdx
│   │   │   │   ├── meta.json
│   │   │   │   ├── obsidian.mdx
│   │   │   │   ├── onedrive.mdx
│   │   │   │   ├── slack.mdx
│   │   │   ├── native/
│   │   │   │   ├── amazon.mdx
│   │   │   │   ├── google-maps.mdx
│   │   │   │   ├── google-search.mdx
│   │   │   │   ├── index.mdx
│   │   │   │   ├── instagram.mdx
│   │   │   │   ├── meta.json
│   │   │   │   ├── reddit.mdx
│   │   │   │   ├── tiktok.mdx
│   │   │   │   ├── web-crawl.mdx
│   │   │   │   ├── youtube.mdx
│   │   ├── docker-installation/
│   │   │   ├── index.mdx
│   │   │   ├── meta.json
│   │   │   ├── updating.mdx
│   │   ├── how-to/
│   │   │   ├── index.mdx
│   │   │   ├── mcp-server.mdx
│   │   │   ├── meta.json
│   │   │   ├── realtime-collaboration.mdx
│   │   │   ├── web-search.mdx
│   │   │   ├── zero-sync.mdx
│   │   ├── local-models/
│   │   │   ├── index.mdx
│   │   │   ├── lm-studio.mdx
│   │   │   ├── meta.json
│   │   │   ├── ollama.mdx
│   │   │   ├── other-local-servers.mdx
│   │   ├── messaging-channels/
│   │   │   ├── discord.mdx
│   │   │   ├── docker.mdx
│   │   │   ├── index.mdx
│   │   │   ├── meta.json
│   │   │   ├── slack.mdx
│   │   │   ├── telegram.mdx
│   │   │   ├── troubleshooting.mdx
│   │   │   ├── whatsapp.mdx
├── contexts/
│   ├── LocaleContext.tsx
│   ├── anonymous-mode.tsx
│   ├── login-gate.tsx
│   ├── platform-context.tsx
├── contracts/
│   ├── enums/
│   │   ├── connector.ts
│   │   ├── connectorIcons.tsx
│   │   ├── toolIcons.tsx
│   ├── types/
│   │   ├── announcement.types.ts
│   │   ├── anonymous-chat.types.ts
│   │   ├── auth.types.ts
│   │   ├── automation.types.ts
│   │   ├── chat-comments.types.ts
│   │   ├── chat-messages.types.ts
│   │   ├── chat-session-state.types.ts
│   │   ├── chat-threads.types.ts
│   │   ├── connector.types.ts
│   │   ├── document.types.ts
│   │   ├── folder.types.ts
│   │   ├── image-generations.types.ts
│   │   ├── inbox.types.ts
│   │   ├── incentive-tasks.types.ts
│   │   ├── index.ts
│   │   ├── invites.types.ts
│   │   ├── log.types.ts
│   │   ├── mcp.types.ts
│   │   ├── members.types.ts
│   │   ├── model-connections.types.ts
│   │   ├── oauth.types.ts
│   │   ├── pat.types.ts
│   │   ├── permissions.types.ts
│   │   ├── podcast.types.ts
│   │   ├── prompts.types.ts
│   │   ├── public-chat.types.ts
│   │   ├── reports.types.ts
│   │   ├── roles.types.ts
│   │   ├── scraper.types.ts
│   │   ├── stripe.types.ts
│   │   ├── user.types.ts
│   │   ├── video-presentations.types.ts
│   │   ├── workspace.types.ts
├── features/
│   ├── artifacts-library/
│   │   ├── index.ts
│   │   ├── hooks/
│   │   │   ├── use-library-artifacts.ts
│   │   ├── model/
│   │   │   ├── artifact.ts
│   │   ├── ui/
│   │   │   ├── artifact-card.tsx
│   │   │   ├── artifacts-library.tsx
│   │   │   ├── kind-meta.ts
│   │   │   ├── library-image-viewer.tsx
│   │   │   ├── media-viewer-dialog.tsx
│   ├── chat-artifacts/
│   │   ├── index.ts
│   │   ├── hooks/
│   │   │   ├── use-sync-chat-artifacts.ts
│   │   ├── lib/
│   │   │   ├── collect-artifacts.ts
│   │   │   ├── scroll-to-artifact.ts
│   │   ├── model/
│   │   │   ├── artifact.ts
│   │   ├── state/
│   │   │   ├── artifacts-panel.atom.ts
│   │   ├── ui/
│   │   │   ├── artifact-anchor.tsx
│   │   │   ├── artifact-row.tsx
│   │   │   ├── artifacts-panel.tsx
│   │   │   ├── artifacts-toggle-button.tsx
│   ├── chat-messages/
│   │   ├── hitl/
│   │   │   ├── index.ts
│   │   │   ├── types.ts
│   │   │   ├── use-hitl-decision.ts
│   │   │   ├── use-hitl-phase.ts
│   │   │   ├── approval/
│   │   │   │   ├── approval-context.tsx
│   │   │   │   ├── hitl-approval-card.tsx
│   │   │   │   ├── index.ts
│   │   │   │   ├── pending-interrupt-context.tsx
│   │   │   ├── approval-cards/
│   │   │   │   ├── doom-loop-approval.tsx
│   │   │   │   ├── generic-approval.tsx
│   │   │   │   ├── index.ts
│   │   │   ├── edit-panel/
│   │   │   │   ├── edit-panel.atom.ts
│   │   │   │   ├── edit-panel.tsx
│   │   │   │   ├── index.ts
│   │   │   │   ├── fields/
│   │   ├── timeline/
│   │   │   ├── build-timeline.ts
│   │   │   ├── data-renderer.tsx
│   │   │   ├── grouping.ts
│   │   │   ├── index.ts
│   │   │   ├── subagent-rename.ts
│   │   │   ├── timeline-group-row.tsx
│   │   │   ├── timeline.tsx
│   │   │   ├── types.ts
│   │   │   ├── items/
│   │   │   │   ├── index.ts
│   │   │   │   ├── item-header.tsx
│   │   │   │   ├── reasoning-item.tsx
│   │   │   │   ├── tool-call-item.tsx
│   │   │   ├── tool-registry/
│   │   │   │   ├── adapt-props.ts
│   │   │   │   ├── index.ts
│   │   │   │   ├── registry.ts
│   │   │   │   ├── types.ts
│   │   │   │   ├── fallback/
├── hooks/
│   ├── use-activate-chat-thread.ts
│   ├── use-agent-actions-query.ts
│   ├── use-announcements.ts
│   ├── use-automation-eligible-models.ts
│   ├── use-automation-model-eligibility.ts
│   ├── use-automation-runs.ts
│   ├── use-automation.ts
│   ├── use-automations.ts
│   ├── use-chat-session-state.ts
│   ├── use-comments-sync.ts
│   ├── use-comments.ts
│   ├── use-connectors-sync.ts
│   ├── use-debounce.ts
│   ├── use-debounced-value.ts
│   ├── use-document-search.ts
│   ├── use-documents-processing.ts
│   ├── use-documents.ts
│   ├── use-folder-sync.ts
│   ├── use-global-loading.ts
│   ├── use-google-drive-folders.ts
│   ├── use-google-picker.ts
│   ├── use-inbox.ts
│   ├── use-logs.ts
│   ├── use-long-press.ts
│   ├── use-media-query.ts
│   ├── use-messages-sync.ts
│   ├── use-mobile.ts
│   ├── use-mounted.ts
│   ├── use-pats.ts
│   ├── use-platform-shortcut.ts
│   ├── use-platform.ts
│   ├── use-podcast-live.ts
│   ├── use-public-chat-runtime.ts
│   ├── use-public-chat.ts
│   ├── use-run-stream.ts
│   ├── use-scraper-capabilities.ts
│   ├── use-scraper-runs.ts
│   ├── use-search-source-connectors.ts
│   ├── use-session.ts
│   ├── use-thread-mutations.ts
│   ├── use-thread-queries.ts
│   ├── use-typewriter.ts
│   ├── use-zero-document-type-counts.ts
├── i18n/
│   ├── request.ts
│   ├── routing.ts
├── lib/
│   ├── agent-filesystem.ts
│   ├── auth-errors.ts
│   ├── auth-fetch.ts
│   ├── auth-utils.ts
│   ├── blog-faq.ts
│   ├── connector-telemetry.ts
│   ├── desktop-download-utils.ts
│   ├── editor-language.ts
│   ├── env-config.ts
│   ├── error-toast.ts
│   ├── error.ts
│   ├── folder-sync-upload.ts
│   ├── format-date.ts
│   ├── layout-events.ts
│   ├── provider-icons.tsx
│   ├── route-params.ts
│   ├── runtime-auth-config.ts
│   ├── source.ts
│   ├── supported-extensions.ts
│   ├── url.ts
│   ├── user-avatar.ts
│   ├── utils.ts
│   ├── announcements/
│   │   ├── announcements-data.ts
│   │   ├── announcements-storage.ts
│   │   ├── announcements-utils.ts
│   ├── apis/
│   │   ├── agent-actions-api.service.ts
│   │   ├── agent-flags-api.service.ts
│   │   ├── agent-permissions-api.service.ts
│   │   ├── agent-tools-api.service.ts
│   │   ├── anonymous-chat-api.service.ts
│   │   ├── auth-api.service.ts
│   │   ├── automations-api.service.ts
│   │   ├── base-api.service.ts
│   │   ├── chat-comments-api.service.ts
│   │   ├── chat-threads-api.service.ts
│   │   ├── connectors-api.service.ts
│   │   ├── documents-api.service.ts
│   │   ├── folders-api.service.ts
│   │   ├── image-generations-api.service.ts
│   │   ├── incentive-tasks-api.service.ts
│   │   ├── invites-api.service.ts
│   │   ├── logs-api.service.ts
│   │   ├── members-api.service.ts
│   │   ├── model-connections-api.service.ts
│   │   ├── notifications-api.service.ts
│   │   ├── pats-api.service.ts
│   │   ├── permissions-api.service.ts
│   │   ├── podcasts-api.service.ts
│   │   ├── prompts-api.service.ts
│   │   ├── public-chat-api.service.ts
│   │   ├── reports-api.service.ts
│   │   ├── roles-api.service.ts
│   │   ├── scrapers-api.service.ts
│   │   ├── stripe-api.service.ts
│   │   ├── user-api.service.ts
│   │   ├── video-presentations-api.service.ts
│   │   ├── workspaces-api.service.ts
│   ├── automations/
│   │   ├── builder-schema.ts
│   │   ├── describe-cron.ts
│   │   ├── run-duration.ts
│   │   ├── schedule-builder.ts
│   ├── chat/
│   │   ├── chat-error-classifier.ts
│   │   ├── chat-request-errors.ts
│   │   ├── display-media-capture.ts
│   │   ├── example-prompts.ts
│   │   ├── mention-doc-key.ts
│   │   ├── message-utils.ts
│   │   ├── parse-mention-segments.ts
│   │   ├── stream-flush.ts
│   │   ├── stream-pipeline.ts
│   │   ├── stream-side-effects.ts
│   │   ├── streaming-state.ts
│   │   ├── thread-cache.ts
│   │   ├── thread-persistence.ts
│   │   ├── user-turn-api-parts.ts
│   │   ├── virtual-path-display.ts
│   │   ├── stream-engine/
│   │   │   ├── engine.ts
│   │   │   ├── helpers.ts
│   │   │   ├── store.ts
│   │   │   ├── use-chat-stream.ts
│   ├── citations/
│   │   ├── citation-parser.ts
│   ├── comments/
│   │   ├── utils.ts
│   ├── connectors/
│   │   ├── utils.ts
│   ├── connectors-marketing/
│   │   ├── amazon.tsx
│   │   ├── google-maps.tsx
│   │   ├── google-search.tsx
│   │   ├── index.ts
│   │   ├── instagram.tsx
│   │   ├── reddit.tsx
│   │   ├── tiktok.tsx
│   │   ├── types.ts
│   │   ├── web-crawl.tsx
│   │   ├── youtube.tsx
│   ├── documents/
│   │   ├── document-type-labels.ts
│   ├── markdown/
│   │   ├── code-regions.ts
│   ├── mcp/
│   │   ├── clients.ts
│   ├── playground/
│   │   ├── catalog.ts
│   │   ├── code-snippets.selfcheck.ts
│   │   ├── code-snippets.ts
│   │   ├── csv.selfcheck.ts
│   │   ├── csv.ts
│   │   ├── format.ts
│   │   ├── json-schema.selfcheck.ts
│   │   ├── json-schema.ts
│   │   ├── platform-icons.tsx
│   │   ├── platform-overrides/
│   │   │   ├── amazon.tsx
│   ├── posthog/
│   │   ├── events.ts
│   │   ├── server.ts
│   ├── query-client/
│   │   ├── cache-keys.ts
│   │   ├── client.ts
│   │   ├── query-client.provider.tsx
│   ├── remotion/
│   │   ├── compile-check.ts
│   │   ├── constants.ts
│   │   ├── dom-to-pptx.d.ts
├── messages/
│   ├── en.json
│   ├── es.json
│   ├── hi.json
│   ├── ko.json
│   ├── pt.json
│   ├── zh.json
├── public/
│   ├── ads.txt
│   ├── demo.mp4
│   ├── icon-128.svg
│   ├── logo.png
│   ├── og-image-twitter.png
│   ├── og-image.png
│   ├── announcements/
│   │   ├── automations.png
│   │   ├── competitive-intelligence.png
│   ├── changelog/
│   │   ├── 0.0.11/
│   │   │   ├── header.gif
│   │   ├── 0.0.12/
│   │   │   ├── header.gif
│   ├── connectors/
│   │   ├── airtable.svg
│   │   ├── amazon.svg
│   │   ├── baidu-search.svg
│   │   ├── bookstack.svg
│   │   ├── circleback.svg
│   │   ├── clickup.svg
│   │   ├── confluence.svg
│   │   ├── discord.svg
│   │   ├── dropbox.svg
│   │   ├── elasticsearch.svg
│   │   ├── github.svg
│   │   ├── google-calendar.svg
│   │   ├── google-drive.svg
│   │   ├── google-gmail.svg
│   │   ├── google-maps.svg
│   │   ├── google-search.svg
│   │   ├── instagram.svg
│   │   ├── jira.svg
│   │   ├── linear.svg
│   │   ├── linkup.svg
│   │   ├── luma.svg
│   │   ├── microsoft-teams.svg
│   │   ├── modelcontextprotocol.svg
│   │   ├── notion.svg
│   │   ├── obsidian.svg
│   │   ├── onedrive.svg
│   │   ├── reddit.svg
│   │   ├── searxng.svg
│   │   ├── slack.svg
│   │   ├── tavily.svg
│   │   ├── tiktok.svg
│   │   ├── web.svg
│   │   ├── youtube.svg
│   │   ├── zoom.svg
│   ├── contact/
│   │   ├── world.svg
│   ├── docs/
│   │   ├── langsmith.png
│   │   ├── unstructured.png
│   │   ├── connectors/
│   │   │   ├── airtable/
│   │   │   │   ├── airtable-oauth-integrations.png
│   │   │   │   ├── airtable-register-integration.png
│   │   │   │   ├── airtable-scopes.png
│   │   │   │   ├── airtable-support-info.png
│   │   │   ├── atlassian/
│   │   │   │   ├── atlassian-authorization.png
│   │   │   │   ├── atlassian-create-app.png
│   │   │   │   ├── atlassian-dev-console-access.png
│   │   │   │   ├── atlassian-name-integration.png
│   │   │   │   ├── atlassian-permissions.png
│   │   │   │   ├── confluence/
│   │   │   │   ├── jira/
│   │   │   ├── clickup/
│   │   │   │   ├── clickup-api-settings.png
│   │   │   │   ├── clickup-app-credentials.png
│   │   │   ├── discord/
│   │   │   │   ├── discord-bot-permissions.png
│   │   │   │   ├── discord-bot-settings.png
│   │   │   │   ├── discord-general-info.png
│   │   │   │   ├── discord-oauth2.png
│   │   │   ├── google/
│   │   │   │   ├── google_oauth_client.png
│   │   │   │   ├── google_oauth_config.png
│   │   │   │   ├── google_oauth_people_api.png
│   │   │   │   ├── google_oauth_screen.png
│   │   │   ├── linear/
│   │   │   │   ├── linear-api-settings.png
│   │   │   │   ├── linear-new-application.png
│   │   │   │   ├── linear-oauth-credentials.png
│   │   │   ├── microsoft-teams/
│   │   │   │   ├── azure-api-permissions.png
│   │   │   │   ├── azure-app-overview.png
│   │   │   │   ├── azure-app-registrations.png
│   │   │   │   ├── azure-certificates-created.png
│   │   │   │   ├── azure-certificates-empty.png
│   │   │   │   ├── azure-register-app.png
│   │   │   │   ├── azure-search-app-reg.png
│   │   │   ├── notion/
│   │   │   │   ├── notion-integration-config.png
│   │   │   │   ├── notion-integrations-page.png
│   │   │   │   ├── notion-new-integration-form.png
│   │   │   ├── slack/
│   │   │   │   ├── slack-app-credentials.png
│   │   │   │   ├── slack-create-app.png
│   │   │   │   ├── slack-distribution.png
│   │   │   │   ├── slack-name-workspace.png
│   │   │   │   ├── slack-redirect-urls.png
│   │   │   │   ├── slack-scopes.png
│   ├── homepage/
│   │   ├── comments-audio.webp
│   │   ├── main_demo.webp
│   │   ├── hero_realtime/
│   │   │   ├── InviteJoinFlow.gif
│   │   │   ├── InviteMembersGif.gif
│   │   │   ├── MakeChatSharedGif.gif
│   │   │   ├── RealTimeChatGif.gif
│   │   │   ├── RealTimeChatGif.mp4
│   │   │   ├── RealTimeCommentsFlow.gif
│   │   │   ├── RealTimeCommentsFlow.mp4
│   │   ├── hero_tutorial/
│   │   │   ├── BQnaGif_compressed.gif
│   │   │   ├── BQnaGif_compressed.mp4
│   │   │   ├── BSNCGif.gif
│   │   │   ├── BSNCGif.mp4
│   │   │   ├── ConnectorFlowGif.gif
│   │   │   ├── ConnectorFlowGif.mp4
│   │   │   ├── DocUploadGif.gif
│   │   │   ├── DocUploadGif.mp4
│   │   │   ├── ImageGenGif.gif
│   │   │   ├── ImageGenGif.mp4
│   │   │   ├── LoginFlowGif.gif
│   │   │   ├── PodcastGenGif.gif
│   │   │   ├── PodcastGenGif.mp4
│   │   │   ├── ReportGenGif_compressed.gif
│   │   │   ├── ReportGenGif_compressed.mp4
│   │   │   ├── folder_watch.gif
│   │   │   ├── folder_watch.mp4
│   │   │   ├── general_assist.gif
│   │   │   ├── general_assist.mp4
│   │   │   ├── quick_assist.gif
│   ├── images/
│   │   ├── blog/
│   │   │   ├── agentic-rag-vs-long-context-llms-benchmark/
│   │   │   │   ├── placeholder-01-hero-image.png
│   │   │   │   ├── placeholder-02-architecture-diagram.png
│   │   │   │   ├── placeholder-03-accuracy-bar-chart-dark.png
│   │   │   │   ├── placeholder-03-accuracy-bar-chart-light.png
│   │   │   │   ├── placeholder-04-cost-vs-accuracy-dark.png
│   │   │   │   ├── placeholder-04-cost-vs-accuracy-light.png
│   │   │   │   ├── placeholder-05-decision-tree.png
│   │   │   ├── no-login-ai-privacy-reality-check/
│   │   │   │   ├── placeholder-01-no-login-vs-no-tracking-hero.png
│   │   │   │   ├── placeholder-02-three-tier-pyramid.png
│   │   │   │   ├── placeholder-03-what-providers-log-conceptual.png
│   │   │   │   ├── placeholder-04-decision-tree-by-use-case.png
│   ├── logos/
│   │   ├── berkeley.svg
│   │   ├── bosta.png
│   │   ├── bristol.svg
│   │   ├── chula.svg
│   │   ├── devoteam.png
│   │   ├── globant.svg
│   │   ├── ironmountain.svg
│   │   ├── koreanair.svg
│   │   ├── leverageedu.png
│   │   ├── nutresa.svg
│   │   ├── opengov.png
│   │   ├── pitt.svg
│   │   ├── tamu.svg
│   │   ├── tec.svg
│   │   ├── tpbank.svg
│   │   ├── usc.svg
│   │   ├── vng.svg
│   │   ├── welab.png
│   │   ├── wisc.svg
│   │   ├── zopper.png
├── tests/
│   ├── README.md
│   ├── auth.setup.ts
│   ├── connectors/
│   │   ├── clickup/
│   │   │   ├── journey.spec.ts
│   │   ├── composio/
│   │   │   ├── calendar/
│   │   │   │   ├── journey.spec.ts
│   │   │   ├── drive/
│   │   │   │   ├── README.md
│   │   │   │   ├── journey.spec.ts
│   │   │   ├── gmail/
│   │   │   │   ├── journey.spec.ts
│   │   ├── confluence/
│   │   │   ├── journey.spec.ts
│   │   ├── dropbox/
│   │   │   ├── journey.spec.ts
│   │   ├── google/
│   │   │   ├── calendar/
│   │   │   │   ├── journey.spec.ts
│   │   │   ├── drive/
│   │   │   │   ├── journey.spec.ts
│   │   │   ├── gmail/
│   │   │   │   ├── journey.spec.ts
│   │   ├── jira/
│   │   │   ├── journey.spec.ts
│   │   ├── linear/
│   │   │   ├── journey.spec.ts
│   │   ├── notion/
│   │   │   ├── journey.spec.ts
│   │   ├── onedrive/
│   │   │   ├── journey.spec.ts
│   │   ├── slack/
│   │   │   ├── journey.spec.ts
│   ├── documents/
│   │   ├── file-upload/
│   │   │   ├── journey.spec.ts
│   │   │   ├── fixtures/
│   │   │   │   ├── canary.md
│   │   │   │   ├── canary.pdf
│   ├── fixtures/
│   │   ├── chat-thread.fixture.ts
│   │   ├── index.ts
│   │   ├── workspace.fixture.ts
│   │   ├── connectors/
│   │   │   ├── clickup.fixture.ts
│   │   │   ├── composio-calendar.fixture.ts
│   │   │   ├── composio-drive.fixture.ts
│   │   │   ├── composio-gmail.fixture.ts
│   │   │   ├── confluence.fixture.ts
│   │   │   ├── jira.fixture.ts
│   │   │   ├── linear.fixture.ts
│   │   │   ├── native-calendar.fixture.ts
│   │   │   ├── native-drive.fixture.ts
│   │   │   ├── native-dropbox.fixture.ts
│   │   │   ├── native-gmail.fixture.ts
│   │   │   ├── native-onedrive.fixture.ts
│   │   │   ├── notion.fixture.ts
│   │   │   ├── slack.fixture.ts
│   ├── helpers/
│   │   ├── canary.ts
│   │   ├── api/
│   │   │   ├── auth.ts
│   │   │   ├── chat.ts
│   │   │   ├── connectors.ts
│   │   │   ├── documents.ts
│   │   │   ├── workspaces.ts
│   │   ├── mocks/
│   │   │   ├── composio-oauth.ts
│   │   ├── ui/
│   │   │   ├── composio-drive-config.ts
│   │   │   ├── connector-popup.ts
│   │   │   ├── connector-status.ts
│   │   │   ├── dashboard.ts
│   │   ├── waits/
│   │   │   ├── indexing.ts
│   ├── smoke/
│   │   ├── chat-stream.spec.ts
│   │   ├── dashboard.spec.ts
├── types/
│   ├── fuzzy-search.d.ts
│   ├── window.d.ts
│   ├── zero.d.ts
├── zero/
│   ├── queries/
│   │   ├── authz.ts
│   │   ├── automations.ts
│   │   ├── chat.ts
│   │   ├── documents.ts
│   │   ├── folders.ts
│   │   ├── inbox.ts
│   │   ├── index.ts
│   │   ├── podcasts.ts
│   │   ├── user.ts
│   ├── schema/
│   │   ├── automations.ts
│   │   ├── chat.ts
│   │   ├── documents.ts
│   │   ├── folders.ts
│   │   ├── inbox.ts
│   │   ├── index.ts
│   │   ├── podcasts.ts
│   │   ├── user.ts
```

### surfsense_browser_extension

```
surfsense_browser_extension/
├── .env.example
├── .gitignore
├── README.md
├── biome.json
├── content.ts
├── font.css
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── popup.tsx
├── postcss.config.js
├── tailwind.config.js
├── tailwind.css
├── tsconfig.json
├── tsconfig.tsbuildinfo
├── assets/
│   ├── brain.png
│   ├── icon.png
├── background/
│   ├── index.ts
│   ├── messages/
│   │   ├── savedata.ts
│   │   ├── savesnapshot.ts
├── lib/
│   ├── utils.ts
├── routes/
│   ├── index.tsx
│   ├── pages/
│   │   ├── ApiKeyForm.tsx
│   │   ├── HomePage.tsx
│   │   ├── Loading.tsx
│   ├── ui/
│   │   ├── button.tsx
│   │   ├── command.tsx
│   │   ├── connection-settings-button.tsx
│   │   ├── dialog.tsx
│   │   ├── label.tsx
│   │   ├── popover.tsx
│   │   ├── toast.tsx
│   │   ├── toaster.tsx
│   │   ├── use-toast.tsx
├── utils/
│   ├── backend-url.ts
│   ├── commons.ts
│   ├── interfaces.ts
```

### surfsense_desktop

```
surfsense_desktop/
├── .env.example
├── .gitignore
├── .npmrc
├── README.md
├── electron-builder.yml
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── tsconfig.json
├── assets/
│   ├── icon-128.png
│   ├── icon.icns
│   ├── icon.ico
│   ├── icon.png
│   ├── iconTemplate.png
│   ├── iconTemplate@2x.png
│   ├── icons/
│   │   ├── 1024x1024.png
│   │   ├── 128x128.png
│   │   ├── 16x16.png
│   │   ├── 256x256.png
│   │   ├── 32x32.png
│   │   ├── 48x48.png
│   │   ├── 512x512.png
│   │   ├── 64x64.png
├── scripts/
│   ├── build-electron.mjs
│   ├── electron-dev.mjs
│   ├── postinstall-rebuild.mjs
├── src/
│   ├── main.ts
│   ├── preload.ts
│   ├── ipc/
│   │   ├── channels.ts
│   │   ├── handlers.ts
│   ├── modules/
│   │   ├── active-workspace.ts
│   │   ├── agent-filesystem-tree-watcher.ts
│   │   ├── agent-filesystem.ts
│   │   ├── analytics.ts
│   │   ├── auth-cutover.ts
│   │   ├── auto-launch.ts
│   │   ├── auto-updater.ts
│   │   ├── deep-links.ts
│   │   ├── errors.ts
│   │   ├── folder-watcher.ts
│   │   ├── general-assist.ts
│   │   ├── menu.ts
│   │   ├── migrate-watched-folders.test.ts
│   │   ├── migrate-watched-folders.ts
│   │   ├── oauth-page.ts
│   │   ├── oauth.ts
│   │   ├── permissions.ts
│   │   ├── platform.ts
│   │   ├── quick-ask.ts
│   │   ├── secret-store.ts
│   │   ├── server.ts
│   │   ├── shortcuts.ts
│   │   ├── tray.ts
│   │   ├── window.ts
│   │   ├── screen-capture/
│   │   │   ├── index.ts
│   │   │   ├── screen-region-picker.ts
│   │   │   ├── screen-region-preload.ts
│   │   │   ├── screenshot-assist.ts
│   │   │   ├── window-picker-preload.ts
│   │   │   ├── window-picker.ts
```

### surfsense_obsidian

```
surfsense_obsidian/
├── .editorconfig
├── .gitignore
├── .npmrc
├── AGENTS.md
├── LICENSE
├── README.md
├── esbuild.config.mjs
├── eslint.config.mts
├── manifest.json
├── package-lock.json
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── styles.css
├── tsconfig.json
├── version-bump.mjs
├── versions.json
├── src/
│   ├── api-client.ts
│   ├── attachments-confirm-modal.ts
│   ├── excludes.ts
│   ├── folder-suggest-modal.ts
│   ├── main.ts
│   ├── payload.ts
│   ├── queue.ts
│   ├── settings.ts
│   ├── status-bar.ts
│   ├── status-modal.ts
│   ├── status-visuals.ts
│   ├── sync-engine.ts
│   ├── types.ts
│   ├── vault-identity.ts
```

### surfsense_mcp

```
surfsense_mcp/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── pyproject.toml
├── uv.lock
├── mcp_server/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── selfcheck.py
│   ├── server.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── errors.py
│   │   ├── rendering.py
│   │   ├── workspace_context.py
│   │   ├── workspace_matching.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── headers.py
│   │   │   ├── identity.py
│   │   │   ├── middleware.py
│   │   ├── transport/
│   │   │   ├── __init__.py
│   │   │   ├── http.py
│   ├── features/
│   │   ├── __init__.py
│   │   ├── knowledge_base/
│   │   │   ├── __init__.py
│   │   │   ├── annotations.py
│   │   │   ├── document_tools.py
│   │   │   ├── note_ingestion.py
│   │   │   ├── search_tools.py
│   │   ├── scrapers/
│   │   │   ├── __init__.py
│   │   │   ├── annotations.py
│   │   │   ├── capability.py
│   │   │   ├── run_history.py
│   │   │   ├── platforms/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── amazon.py
│   │   │   │   ├── google_maps.py
│   │   │   │   ├── google_search.py
│   │   │   │   ├── instagram.py
│   │   │   │   ├── reddit.py
│   │   │   │   ├── tiktok.py
│   │   │   │   ├── web.py
│   │   │   │   ├── youtube.py
│   │   ├── workspaces/
│   │   │   ├── __init__.py
├── tests/
│   ├── test_auth_headers.py
│   ├── test_client_errors.py
│   ├── test_client_params.py
│   ├── test_note_ingestion.py
│   ├── test_rendering.py
│   ├── test_request_auth.py
│   ├── test_workspace_context.py
```

### surfsense_evals

```
surfsense_evals/
├── .env.example
├── .gitignore
├── README.md
├── pyproject.toml
├── uv.lock
├── data/
│   ├── .gitignore
│   ├── multimodal_doc/
│   │   ├── runs/
│   │   │   ├── 2026-05-14T00-53-19Z/
│   │   │   │   ├── parser_compare/
├── reports/
│   ├── .gitignore
├── scripts/
│   ├── analyze_failure_timing.py
│   ├── analyze_failures.py
│   ├── check_extraction_sizes.py
│   ├── check_uploaded_status.py
│   ├── compute_adjusted_accuracy.py
│   ├── compute_blog_extras.py
│   ├── compute_post_retry_accuracy.py
│   ├── inspect_first30.py
│   ├── patch_manifest_for_parallel_ingest.py
│   ├── peek_crag_run.py
│   ├── peek_disagreements.py
│   ├── retry_failed_questions.py
│   ├── summarise_crag_run.py
│   ├── summarise_parser_compare_run.py
│   ├── test_context_overflow_hypothesis.py
├── src/
│   ├── surfsense_evals/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── cli.py
│   │   │   ├── config.py
│   │   │   ├── ingest_settings.py
│   │   │   ├── registry.py
│   │   │   ├── scenarios.py
│   │   │   ├── vision_llm.py
│   │   │   ├── arms/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── bare_llm.py
│   │   │   │   ├── base.py
│   │   │   │   ├── native_pdf.py
│   │   │   │   ├── surfsense.py
│   │   │   ├── clients/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── documents.py
│   │   │   │   ├── new_chat.py
│   │   │   │   ├── search_space.py
│   │   │   ├── metrics/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── comparison.py
│   │   │   │   ├── mc_accuracy.py
│   │   │   │   ├── retrieval.py
│   │   │   ├── parse/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── answer_letter.py
│   │   │   │   ├── citations.py
│   │   │   │   ├── freeform_answer.py
│   │   │   │   ├── sse.py
│   │   │   ├── parsers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── azure_di.py
│   │   │   │   ├── llamacloud.py
│   │   │   │   ├── pdf_pages.py
│   │   │   ├── pdf/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── render.py
│   │   │   ├── providers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── openrouter_chat.py
│   │   │   │   ├── openrouter_pdf.py
│   │   │   ├── report/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── writer.py
│   │   ├── suites/
│   │   │   ├── __init__.py
│   │   │   ├── _demo/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── hello/
│   │   │   ├── medical/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── cure/
│   │   │   │   ├── medxpertqa/
│   │   │   │   ├── mirage/
│   │   │   ├── multimodal_doc/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── mmlongbench/
│   │   │   │   ├── parser_compare/
│   │   │   ├── research/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── crag/
│   │   │   │   ├── frames/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_integration_smoke.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── test_auth.py
│   │   ├── test_clients.py
│   │   ├── test_config.py
│   │   ├── test_ingest_settings.py
│   │   ├── test_metrics.py
│   │   ├── test_parse_answer_letter.py
│   │   ├── test_parse_citations.py
│   │   ├── test_parse_freeform_answer.py
│   │   ├── test_parse_sse.py
│   │   ├── test_pdf_render.py
│   │   ├── test_pdf_render_with_images.py
│   │   ├── test_provider_openrouter.py
│   │   ├── test_registry.py
│   │   ├── test_scenarios.py
│   │   ├── test_vision_llm.py
│   ├── suites/
│   │   ├── __init__.py
│   │   ├── test_crag_dataset.py
│   │   ├── test_crag_grader.py
│   │   ├── test_crag_html_extract.py
│   │   ├── test_frames_dataset.py
│   │   ├── test_frames_grader.py
│   │   ├── test_frames_wiki_fetch.py
│   │   ├── test_mmlongbench_grader.py
```

## Thư mục quan trọng

| Phần | Thư mục | Mục đích |
|---|---|---|
| backend | `app/routes/` | Các FastAPI route/endpoint |
| backend | `app/db.py` | SQLAlchemy Base & models chính |
| backend | `app/capabilities/` | Scraper API cho các nền tảng |
| backend | `app/agents/` | Multi-agent chat & runtime |
| backend | `app/indexing_pipeline/` | Xử lý và index tài liệu |
| backend | `app/retriever/` | Hybrid search (semantic + full-text) |
| backend | `alembic/versions/` | Database migrations |
| web | `app/dashboard/` | Giao diện dashboard chính |
| web | `app/(home)/` | Landing pages & marketing |
| web | `components/` | React components |
| web | `lib/` | Utilities, API client, hooks |
| web | `atoms/` | Jotai state atoms |
| browser_extension | `background/`, `routes/` | Service worker & UI |
| desktop | `src/main.ts`, `src/ipc/` | Main process & IPC |
| obsidian | `src/` | Plugin source |
| mcp | `mcp_server/` | MCP server implementation |
| evals | `src/surfsense_evals/` | Core evaluation harness |

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
