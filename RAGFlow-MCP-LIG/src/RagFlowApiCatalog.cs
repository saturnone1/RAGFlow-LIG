public static class RagFlowApiCatalog
{
    public static object Describe() => new
    {
        scope = "/api/v1",
        version = "RAGFlow v0.26.4",
        coverage = "All /api/v1 routes are callable through the generic tools; the catalog groups the complete public route families and their principal operations.",
        guidance = new[]
        {
            "Use rag_flow_api_request for JSON and text responses.",
            "Use upload_rag_flow_api_files for multipart upload endpoints.",
            "Use download_rag_flow_api_response for documents, attachments, audio, and other binary responses.",
            "Pass a relativePath beginning with api/v1/. Query strings may be included.",
            "Requests other than GET and HEAD require RAGFLOW_WRITES_ENABLED=true.",
            "Local downloads require RAGFLOW_FILE_WRITES_ENABLED=true.",
            "Completion endpoints must use stream=false; SSE must be consumed directly from RAGFlow."
        },
        categories = new Dictionary<string, string[]>
        {
            ["datasets"] =
            [
                "POST /api/v1/datasets", "GET /api/v1/datasets", "GET /api/v1/datasets/{dataset_id}",
                "PUT /api/v1/datasets/{dataset_id}", "DELETE /api/v1/datasets",
                "GET|DELETE /api/v1/datasets/{dataset_id}/graph", "POST|GET /api/v1/datasets/{dataset_id}/index?type=graph|raptor",
                "POST /api/v1/datasets/search", "POST /api/v1/datasets/{dataset_id}/search",
                "GET /api/v1/datasets/tags/aggregation", "GET /api/v1/datasets/metadata/flattened",
                "GET|PUT|DELETE /api/v1/datasets/{dataset_id}/tags", "GET|DELETE /api/v1/datasets/{dataset_id}/artifacts",
                "GET /api/v1/datasets/{dataset_id}/artifacts/graph", "GET|PUT /api/v1/datasets/{dataset_id}/artifacts/{page_type}/{slug}",
                "GET /api/v1/datasets/{dataset_id}/skills", "GET /api/v1/datasets/{dataset_id}/skills/{skill_kwd}",
                "POST /api/v1/datasets/{dataset_id}/embedding", "POST /api/v1/datasets/{dataset_id}/embedding/check",
                "GET /api/v1/datasets/{dataset_id}/ingestions", "GET /api/v1/datasets/{dataset_id}/ingestions/{log_id}",
                "GET|PUT /api/v1/datasets/{dataset_id}/metadata/config"
            ],
            ["documents_and_chunks"] =
            [
                "POST|GET|DELETE /api/v1/datasets/{dataset_id}/documents", "GET|PATCH /api/v1/datasets/{dataset_id}/documents/{document_id}",
                "POST /api/v1/datasets/{dataset_id}/documents/parse", "POST /api/v1/datasets/{dataset_id}/documents/stop",
                "POST|GET|PATCH|DELETE /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
                "GET|PATCH /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/{chunk_id}",
                "POST /api/v1/documents/ingest", "GET /api/v1/datasets/{dataset_id}/metadata/summary", "POST /api/v1/datasets/{dataset_id}/metadata/update",
                "POST /api/v1/retrieval",
                "POST /api/v1/documents/upload", "GET /api/v1/documents/{document_id}", "GET /api/v1/documents/{document_id}/preview",
                "GET /api/v1/documents/images/{image_id}", "GET /api/v1/documents/artifact/{filename}", "GET /api/v1/thumbnails",
                "PUT /api/v1/datasets/{dataset_id}/documents/{document_id}/metadata/config",
                "PATCH /api/v1/datasets/{dataset_id}/documents/metadatas", "POST /api/v1/datasets/{dataset_id}/documents/batch-update-status",
                "GET|DELETE /api/v1/datasets/{dataset_id}/documents/{document_id}/structure/graph"
            ],
            ["chats_and_sessions"] =
            [
                "POST|GET|DELETE /api/v1/chats", "GET|PUT|PATCH|DELETE /api/v1/chats/{chat_id}",
                "POST|GET|DELETE /api/v1/chats/{chat_id}/sessions", "GET|PATCH /api/v1/chats/{chat_id}/sessions/{session_id}",
                "POST /api/v1/chat/completions", "POST /api/v1/openai/{chat_id}/chat/completions",
                "DELETE /api/v1/chats/{chat_id}/sessions/{session_id}/messages/{msg_id}",
                "PUT /api/v1/chats/{chat_id}/sessions/{session_id}/messages/{msg_id}/feedback",
                "POST /api/v1/chat/audio/speech", "POST /api/v1/chat/audio/transcription", "POST /api/v1/chat/mindmap", "POST /api/v1/chat/recommendation"
            ],
            ["public_bots"] =
            [
                "POST /api/v1/chatbots/{dialog_id}/completions", "GET /api/v1/chatbots/{dialog_id}/info",
                "POST /api/v1/agentbots/{agent_id}/completions", "GET /api/v1/agentbots/{agent_id}/inputs", "GET /api/v1/agentbots/{shared_id}/logs/{message_id}",
                "POST /api/v1/searchbots/ask", "POST /api/v1/searchbots/retrieval_test", "POST /api/v1/searchbots/related_questions",
                "GET /api/v1/searchbots/detail", "POST /api/v1/searchbots/mindmap"
            ],
            ["agents"] =
            [
                "POST|GET /api/v1/agents", "GET|PUT|DELETE /api/v1/agents/{agent_id}",
                "POST|GET|DELETE /api/v1/agents/{agent_id}/sessions", "GET|DELETE /api/v1/agents/{agent_id}/sessions/{session_id}",
                "POST /api/v1/agents/chat/completions", "POST /api/v1/agents_openai/{agent_id}/chat/completions",
                "GET /api/v1/agents/{agent_id}/versions", "GET /api/v1/agents/{agent_id}/logs/{message_id}",
                "GET /api/v1/agents/download", "GET /api/v1/agents/templates", "GET /api/v1/agents/prompts", "GET /api/v1/agents/tags", "PUT /api/v1/agents/{canvas_id}/tags",
                "POST /api/v1/agents/{agent_id}/upload", "GET /api/v1/agents/{agent_id}/components/{component_id}/input-form",
                "POST /api/v1/agents/{agent_id}/components/{component_id}/debug", "GET /api/v1/agents/{agent_id}/versions/{version_id}",
                "POST /api/v1/agents/{agent_id}/reset", "POST /api/v1/agents/rerun", "POST /api/v1/agents/test_db_connection",
                "GET|HEAD|POST|PUT|PATCH|DELETE /api/v1/agents/{agent_id}/webhook", "GET|HEAD|POST|PUT|PATCH|DELETE /api/v1/agents/{agent_id}/webhook/test", "GET /api/v1/agents/{agent_id}/webhook/logs",
                "GET /api/v1/agents/attachments/{attachment_id}/preview", "GET /api/v1/agents/attachments/{attachment_id}/download"
            ],
            ["memories"] =
            [
                "POST|GET /api/v1/memories", "GET|PUT|DELETE /api/v1/memories/{memory_id}", "GET /api/v1/memories/{memory_id}/config",
                "POST|GET /api/v1/messages", "GET /api/v1/messages/search", "GET|PUT|DELETE /api/v1/messages/{memory_id}:{message_id}",
                "GET /api/v1/messages/{memory_id}:{message_id}/content"
            ],
            ["files_and_commits"] =
            [
                "POST|GET|DELETE /api/v1/files", "GET /api/v1/files/{file_id}", "POST /api/v1/files/move",
                "GET /api/v1/files/{file_id}/parent", "GET /api/v1/files/{file_id}/ancestors", "POST /api/v1/files/link-to-datasets",
                "POST|GET /api/v1/folders/{folder_id}/commits", "GET /api/v1/folders/{folder_id}/commits/{commit_id}",
                "GET /api/v1/folders/{folder_id}/commits/diff", "GET /api/v1/folders/{folder_id}/changes",
                "The same commit operations are available below /datasets/{dataset_id} and /workspace/{folder_id}",
                "GET /api/v1/files/{file_id}/versions"
            ],
            ["search_apps"] =
            [
                "POST|GET /api/v1/searches", "GET|PUT|DELETE /api/v1/searches/{search_id}", "POST /api/v1/searches/{search_id}/completions"
            ],
            ["models_and_providers"] =
            [
                "GET /api/v1/models", "GET|PATCH /api/v1/models/default", "GET|PUT /api/v1/providers",
                "GET|DELETE /api/v1/providers/{provider}", "GET /api/v1/providers/{provider}/models",
                "POST|GET|DELETE /api/v1/providers/{provider}/instances", "POST /api/v1/providers/{provider}/connection",
                "GET /api/v1/providers/{provider}/instances/{instance}",
                "GET|PUT|POST /api/v1/providers/{provider}/instances/{instance}/models",
                "PATCH|POST /api/v1/providers/{provider}/instances/{instance}/models/{model_name}"
            ],
            ["mcp_connectors_and_channels"] =
            [
                "POST|GET /api/v1/mcp/servers", "GET|PUT|DELETE /api/v1/mcp/servers/{mcp_id}",
                "POST /api/v1/mcp/servers/import", "POST /api/v1/mcp/servers/{mcp_id}/test",
                "POST|GET /api/v1/connectors", "GET|PATCH|DELETE /api/v1/connectors/{connector_id}",
                "GET /api/v1/connectors/{connector_id}/logs", "POST /api/v1/connectors/{connector_id}/test", "POST /api/v1/connectors/{connector_id}/rebuild",
                "POST|GET /api/v1/chat-channels", "GET|PATCH|DELETE /api/v1/chat-channels/{channel_id}",
                "GET /api/v1/chat-channels/{channel_id}/runtime",
                "POST /api/v1/connectors/google/oauth/web/start", "GET /api/v1/connectors/gmail/oauth/web/callback",
                "GET /api/v1/connectors/google-drive/oauth/web/callback", "POST /api/v1/connectors/google/oauth/web/result",
                "POST /api/v1/connectors/box/oauth/web/start", "GET /api/v1/connectors/box/oauth/web/callback", "POST /api/v1/connectors/box/oauth/web/result"
            ],
            ["compilation_tasks_plugins_and_observability"] =
            [
                "GET /api/v1/compilation_templates/builtins", "GET /api/v1/compilation_templates/wiki_presets",
                "GET|POST /api/v1/compilation_template_groups", "GET|PUT|DELETE /api/v1/compilation_template_groups/{group_id}",
                "POST /api/v1/tasks/{task_id}/cancel", "PATCH /api/v1/tasks/{task_id}", "GET /api/v1/plugin/tools",
                "GET|POST|PUT|DELETE /api/v1/langfuse/api-key", "GET|POST /api/v1/dify/retrieval", "GET /api/v1/dify/retrieval/health"
            ],
            ["authentication"] =
            [
                "POST /api/v1/auth/login", "GET /api/v1/auth/login/channels", "GET /api/v1/auth/login/{channel}",
                "GET /api/v1/auth/oauth/{channel}/callback", "POST /api/v1/auth/logout",
                "POST /api/v1/auth/password/forgot/captcha", "POST /api/v1/auth/password/forgot/otp",
                "POST /api/v1/auth/password/forgot/otp/verify", "POST /api/v1/auth/password/reset"
            ],
            ["teams_users_and_system"] =
            [
                "GET /api/v1/tenants", "PATCH /api/v1/tenants/{tenant_id}", "GET|POST|DELETE /api/v1/tenants/{tenant_id}/users",
                "GET|PATCH /api/v1/users/me", "GET|PATCH /api/v1/users/me/models", "POST /api/v1/users",
                "GET /api/v1/system/ping", "GET /api/v1/system/version", "GET /api/v1/system/status", "GET /api/v1/system/stats",
                "GET /api/v1/system/config", "GET|POST /api/v1/system/tokens", "DELETE /api/v1/system/tokens/{token}", "GET|PUT /api/v1/system/config/log"
            ]
        }
    };
}
