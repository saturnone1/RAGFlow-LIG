using ModelContextProtocol.Server;
using System.ComponentModel;
using System.Text.Json;

public sealed class RagFlowTools
{
    private readonly RagFlowClient _client;
    private readonly RagFlowSettings _settings;
    public RagFlowTools(RagFlowClient client, RagFlowSettings settings) { _client = client; _settings = settings; }

    [McpServerTool(ReadOnly = true), Description("Check the RAGFlow endpoint and adapter configuration without exposing the API key.")]
    public Task<RagFlowHealth> RagFlowConfig() => _client.HealthAsync();

    [McpServerTool(ReadOnly = true), Description("List the RAGFlow v0.26.4 API areas and routes available through the generic MCP API tools.")]
    public object RagFlowApiCatalog() => global::RagFlowApiCatalog.Describe();

    [McpServerTool, Description("Call any non-streaming RAGFlow /api/v1 JSON or text endpoint. Use a relative path such as api/v1/models or api/v1/retrieval. Set stream=false for completion APIs. Non-GET methods require writes to be enabled.")]
    public Task<JsonElement> RagFlowApiRequest(string method, string relativePath, string? bodyJson = null)
        => _client.RequestAsync(method, relativePath, bodyJson);

    [McpServerTool, Description("Upload one or more local files to any multipart RAGFlow /api/v1 endpoint. formFieldsJson must be a JSON object when supplied.")]
    public Task<JsonElement> UploadRagFlowApiFiles(string relativePath, string[] filePaths, string fieldName = "file", string? formFieldsJson = null)
        => _client.UploadFilesAsync(relativePath, filePaths, fieldName, formFieldsJson);

    [McpServerTool, Description("Save a binary or text response from any RAGFlow /api/v1 endpoint to a local absolute path. Requires RAGFLOW_FILE_WRITES_ENABLED=true. Existing files are preserved unless overwrite=true.")]
    public Task<object> DownloadRagFlowApiResponse(string method, string relativePath, string destinationPath, string? bodyJson = null, bool overwrite = false)
        => _client.DownloadAsync(method, relativePath, destinationPath, bodyJson, overwrite);

    [McpServerTool(ReadOnly = true), Description("List RAGFlow datasets, optionally filtering by name and paginating.")]
    public Task<JsonElement> ListRagFlowDatasets(string? name = null, int page = 1, int pageSize = 100)
        => _client.GetAsync($"api/v1/datasets?page={Math.Max(1, page)}&page_size={Math.Clamp(pageSize, 1, 1000)}&name={Uri.EscapeDataString(name ?? "")}");

    [McpServerTool, Description("Create a RAGFlow dataset using the tenant default embedding model.")]
    public Task<JsonElement> CreateRagFlowDataset(string name, string description = "", string permission = "me", string chunkMethod = "naive", int chunkTokenNum = 512)
    {
        _settings.RequireWrites();
        return _client.PostAsync("api/v1/datasets", new { name, description, permission, chunk_method = chunkMethod, parser_config = new { chunk_token_num = Math.Clamp(chunkTokenNum, 1, 2048), delimiter = "\n", layout_recognize = "DeepDOC", task_page_size = 6, auto_keywords = 0, auto_questions = 0, html4excel = false, raptor = new { use_raptor = false }, graphrag = new { use_graphrag = false } } });
    }

    [McpServerTool, Description("Update a RAGFlow dataset. Pass only fields that should change.")]
    public Task<JsonElement> UpdateRagFlowDataset(string datasetId, string? name = null, string? description = null, string? permission = null)
    {
        _settings.RequireWrites();
        var body = new Dictionary<string, object?>();
        if (name is not null) body["name"] = name;
        if (description is not null) body["description"] = description;
        if (permission is not null) body["permission"] = permission;
        return _client.PutAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}", body);
    }

    [McpServerTool, Description("Delete a RAGFlow dataset and its documents, chunks, and index data.")]
    public Task<JsonElement> DeleteRagFlowDataset(string datasetId)
    { _settings.RequireWrites(); return _client.DeleteAsync("api/v1/datasets", new { ids = new[] { datasetId } }); }

    [McpServerTool(ReadOnly = true), Description("List documents in a RAGFlow dataset with status, progress, chunk, and token counts.")]
    public Task<JsonElement> ListRagFlowDocuments(string datasetId, string? name = null, int page = 1, int pageSize = 100)
        => _client.GetAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/documents?page={Math.Max(1, page)}&page_size={Math.Clamp(pageSize, 1, 1000)}&name={Uri.EscapeDataString(name ?? "")}");

    [McpServerTool, Description("Upload any supported local file to a RAGFlow dataset. Absolute paths on any accessible Windows drive are accepted.")]
    public Task<JsonElement> UploadRagFlowDocument(string datasetId, string filePath)
    { _settings.RequireWrites(); return _client.UploadAsync(datasetId, filePath); }

    [McpServerTool, Description("Update a RAGFlow document name, metadata JSON, or chunk method.")]
    public Task<JsonElement> UpdateRagFlowDocument(string datasetId, string documentId, string? name = null, string? metadataJson = null, string? chunkMethod = null)
    {
        _settings.RequireWrites();
        var body = new Dictionary<string, object?>();
        if (name is not null) body["name"] = name;
        if (metadataJson is not null) body["meta_fields"] = JsonSerializer.Deserialize<JsonElement>(metadataJson);
        if (chunkMethod is not null) body["chunk_method"] = chunkMethod;
        return _client.PatchAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/documents/{Uri.EscapeDataString(documentId)}", body);
    }

    [McpServerTool, Description("Delete documents and all of their chunks from a RAGFlow dataset.")]
    public Task<JsonElement> DeleteRagFlowDocuments(string datasetId, string[] documentIds)
    { _settings.RequireWrites(); return _client.DeleteAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/documents", new { ids = documentIds }); }

    [McpServerTool, Description("Start or rerun parsing, chunking, embedding, and indexing for documents.")]
    public Task<JsonElement> StartRagFlowParsing(string datasetId, string[] documentIds)
    { _settings.RequireWrites(); return _client.PostAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/chunks", new { document_ids = documentIds }); }

    [McpServerTool, Description("Cancel active parsing for documents.")]
    public Task<JsonElement> StopRagFlowParsing(string datasetId, string[] documentIds)
    { _settings.RequireWrites(); return _client.DeleteAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/chunks", new { document_ids = documentIds }); }

    [McpServerTool(ReadOnly = true), Description("List chunks for one RAGFlow document, optionally filtering by keywords.")]
    public Task<JsonElement> ListRagFlowChunks(string datasetId, string documentId, string? keywords = null, int page = 1, int pageSize = 100)
        => _client.GetAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/documents/{Uri.EscapeDataString(documentId)}/chunks?page={Math.Max(1, page)}&page_size={Math.Clamp(pageSize, 1, 1000)}&keywords={Uri.EscapeDataString(keywords ?? "")}");

    [McpServerTool, Description("Create a manual chunk in a RAGFlow document.")]
    public Task<JsonElement> CreateRagFlowChunk(string datasetId, string documentId, string content, string[]? importantKeywords = null)
    { _settings.RequireWrites(); return _client.PostAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/documents/{Uri.EscapeDataString(documentId)}/chunks", new { content, important_keywords = importantKeywords ?? Array.Empty<string>() }); }

    [McpServerTool, Description("Update chunk content or important keywords. Content changes trigger a new embedding.")]
    public Task<JsonElement> UpdateRagFlowChunk(string datasetId, string documentId, string chunkId, string? content = null, string[]? importantKeywords = null)
    {
        _settings.RequireWrites();
        var body = new Dictionary<string, object?>();
        if (content is not null) body["content"] = content;
        if (importantKeywords is not null) body["important_keywords"] = importantKeywords;
        return _client.PatchAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/documents/{Uri.EscapeDataString(documentId)}/chunks/{Uri.EscapeDataString(chunkId)}", body);
    }

    [McpServerTool, Description("Delete chunks from one RAGFlow document.")]
    public Task<JsonElement> DeleteRagFlowChunks(string datasetId, string documentId, string[] chunkIds)
    { _settings.RequireWrites(); return _client.DeleteAsync($"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/documents/{Uri.EscapeDataString(documentId)}/chunks", new { chunk_ids = chunkIds }); }
}
