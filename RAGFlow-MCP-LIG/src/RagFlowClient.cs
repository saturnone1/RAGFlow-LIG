using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

public sealed class RagFlowClient
{
    private readonly HttpClient _http;
    private readonly RagFlowSettings _settings;
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public RagFlowClient(HttpClient http, RagFlowSettings settings)
    {
        _http = http;
        _settings = settings;
    }

    public async Task<RagFlowHealth> HealthAsync()
    {
        try
        {
            // Health checks must not depend on a tenant API key. In a fresh or
            // air-gapped installation the configured value can still be the
            // bootstrap placeholder. The unauthenticated dependency health
            // endpoint covers the database, queue, document engine and storage.
            using var request = new HttpRequestMessage(HttpMethod.Get, "api/v1/system/healthz");
            using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
            var bytes = await ReadLimitedBytesAsync(response.Content, _settings.MaxTextResponseBytes);
            var available = false;
            if (response.IsSuccessStatusCode)
            {
                using var document = JsonDocument.Parse(bytes);
                available = document.RootElement.ValueKind == JsonValueKind.Object
                    && document.RootElement.TryGetProperty("status", out var status)
                    && string.Equals(status.GetString(), "ok", StringComparison.Ordinal);
            }
            return BuildHealth(available, (int)response.StatusCode, available ? null : "RAGFlow dependency health check failed.");
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException or InvalidOperationException or JsonException)
        {
            return BuildHealth(false, null, "RAGFlow is unreachable or returned an invalid dependency health response.");
        }
    }

    private RagFlowHealth BuildHealth(bool available, int? httpStatus, string? error) => new(
        available ? "ok" : "unavailable",
        available,
        _settings.BaseUrl,
        !string.IsNullOrWhiteSpace(_settings.ApiKey),
        _settings.WritesEnabled,
        _settings.FileWritesEnabled,
        !string.IsNullOrWhiteSpace(_settings.McpApiKey),
        _settings.MaxTextResponseBytes,
        httpStatus,
        error);

    public Task<JsonElement> GetAsync(string path) => SendAsync(HttpMethod.Get, path);
    public Task<JsonElement> PostAsync(string path, object? body = null) => SendAsync(HttpMethod.Post, path, body);
    public Task<JsonElement> PutAsync(string path, object? body = null) => SendAsync(HttpMethod.Put, path, body);
    public Task<JsonElement> PatchAsync(string path, object? body = null) => SendAsync(HttpMethod.Patch, path, body);
    public Task<JsonElement> DeleteAsync(string path, object? body = null) => SendAsync(HttpMethod.Delete, path, body);

    public async Task<JsonElement> GetProjectedCollectionAsync(string path, params string[] fields)
    {
        var response = await GetAsync(path);
        if (response.ValueKind != JsonValueKind.Object
            || !response.TryGetProperty("data", out var payload))
            throw new InvalidOperationException("RAGFlow collection response does not contain data.");

        JsonElement data;
        JsonElement totalValue;
        if (payload.ValueKind == JsonValueKind.Array)
        {
            data = payload;
            response.TryGetProperty("total", out totalValue);
        }
        else if (payload.ValueKind == JsonValueKind.Object
                 && payload.TryGetProperty("docs", out data)
                 && data.ValueKind == JsonValueKind.Array)
        {
            payload.TryGetProperty("total", out totalValue);
        }
        else
        {
            throw new InvalidOperationException("RAGFlow collection response does not contain a supported array.");
        }

        var rows = new List<Dictionary<string, JsonElement>>();
        foreach (var item in data.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object) continue;
            var row = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
            foreach (var field in fields)
            {
                if (item.TryGetProperty(field, out var value)) row[field] = value.Clone();
            }
            rows.Add(row);
        }
        var total = totalValue.ValueKind == JsonValueKind.Number && totalValue.TryGetInt64(out var count)
            ? count
            : rows.Count;
        return JsonSerializer.SerializeToElement(new { total, data = rows }, JsonOptions);
    }

    public async Task<JsonElement> GetDocumentStageTimingsAsync(string datasetId, string documentId)
    {
        var escapedDatasetId = Uri.EscapeDataString(datasetId);
        var escapedDocumentId = Uri.EscapeDataString(documentId);
        var documentResponse = await GetAsync(
            $"api/v1/datasets/{escapedDatasetId}/documents?id={escapedDocumentId}&page=1&page_size=1");
        if (!documentResponse.TryGetProperty("data", out var documentData)
            || documentData.ValueKind != JsonValueKind.Object
            || !documentData.TryGetProperty("docs", out var documents)
            || documents.ValueKind != JsonValueKind.Array
            || documents.GetArrayLength() != 1
            || !documents[0].TryGetProperty("name", out var nameValue))
            throw new InvalidOperationException("RAGFlow did not return the requested document.");

        var name = nameValue.GetString() ?? string.Empty;
        var logResponse = await GetAsync(
            $"api/v1/datasets/{escapedDatasetId}/ingestions?log_type=file&page=1&page_size=100&orderby=create_time&desc=true&keywords={Uri.EscapeDataString(name)}");
        if (!logResponse.TryGetProperty("data", out var ingestionData)
            || ingestionData.ValueKind != JsonValueKind.Object
            || !ingestionData.TryGetProperty("logs", out var logs)
            || logs.ValueKind != JsonValueKind.Array)
            throw new InvalidOperationException("RAGFlow ingestion response does not contain a logs array.");

        string[] fields = [
            "id", "document_id", "document_name", "parser_id", "task_type",
            "operation_status", "progress", "process_begin_at", "process_duration",
            "create_time", "update_time"
        ];
        var rows = new List<Dictionary<string, JsonElement>>();
        foreach (var item in logs.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object
                || !item.TryGetProperty("document_id", out var itemDocumentId)
                || !string.Equals(itemDocumentId.GetString(), documentId, StringComparison.Ordinal))
                continue;
            var row = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
            foreach (var field in fields)
                if (item.TryGetProperty(field, out var value)) row[field] = value.Clone();
            rows.Add(row);
        }
        return JsonSerializer.SerializeToElement(new { total = rows.Count, data = rows }, JsonOptions);
    }

    public Task<JsonElement> RequestAsync(string method, string relativePath, string? bodyJson = null)
    {
        var httpMethod = ParseMethod(method);
        if (httpMethod != HttpMethod.Get && httpMethod != HttpMethod.Head) _settings.RequireWrites();
        return SendJsonAsync(httpMethod, ValidateApiPath(relativePath), bodyJson);
    }

    public async Task<JsonElement> UploadAsync(string datasetId, string filePath)
    {
        _settings.RequireApiKey();
        var fullPath = Path.GetFullPath(filePath);
        if (!File.Exists(fullPath)) throw new FileNotFoundException("Upload file not found.", fullPath);
        using var request = CreateRequest(HttpMethod.Post, $"api/v1/datasets/{Uri.EscapeDataString(datasetId)}/documents");
        using var form = new MultipartFormDataContent();
        await using var stream = File.OpenRead(fullPath);
        using var file = new StreamContent(stream);
        file.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
        form.Add(file, "file", Path.GetFileName(fullPath));
        request.Content = form;
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
        return await ReadResultAsync(response);
    }

    public async Task<JsonElement> UploadFilesAsync(string relativePath, string[] filePaths, string fieldName, string? formFieldsJson)
    {
        _settings.RequireApiKey();
        _settings.RequireWrites();
        if (filePaths.Length == 0) throw new ArgumentException("At least one upload file is required.", nameof(filePaths));
        if (string.IsNullOrWhiteSpace(fieldName)) throw new ArgumentException("Multipart field name is required.", nameof(fieldName));

        using var request = CreateRequest(HttpMethod.Post, ValidateApiPath(relativePath));
        using var form = new MultipartFormDataContent();
        foreach (var filePath in filePaths)
        {
            var fullPath = Path.GetFullPath(filePath);
            if (!File.Exists(fullPath)) throw new FileNotFoundException("Upload file not found.", fullPath);
            var file = new StreamContent(File.OpenRead(fullPath));
            file.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
            form.Add(file, fieldName, Path.GetFileName(fullPath));
        }

        if (!string.IsNullOrWhiteSpace(formFieldsJson))
        {
            using var fields = JsonDocument.Parse(formFieldsJson);
            if (fields.RootElement.ValueKind != JsonValueKind.Object) throw new ArgumentException("formFieldsJson must be a JSON object.", nameof(formFieldsJson));
            foreach (var property in fields.RootElement.EnumerateObject())
            {
                var value = property.Value.ValueKind == JsonValueKind.String ? property.Value.GetString() ?? "" : property.Value.GetRawText();
                form.Add(new StringContent(value, Encoding.UTF8), property.Name);
            }
        }

        request.Content = form;
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
        return await ReadResultAsync(response);
    }

    public async Task<object> DownloadAsync(string method, string relativePath, string destinationPath, string? bodyJson, bool overwrite)
    {
        _settings.RequireApiKey();
        _settings.RequireFileWrites();
        var httpMethod = ParseMethod(method);
        if (httpMethod != HttpMethod.Get && httpMethod != HttpMethod.Head) _settings.RequireWrites();
        var fullPath = Path.GetFullPath(destinationPath);
        if (File.Exists(fullPath) && !overwrite) throw new IOException($"Destination already exists: {fullPath}");
        var parent = Path.GetDirectoryName(fullPath);
        if (string.IsNullOrWhiteSpace(parent) || !Directory.Exists(parent)) throw new DirectoryNotFoundException($"Destination directory not found: {parent}");

        using var request = CreateRequest(httpMethod, ValidateApiPath(relativePath));
        if (!string.IsNullOrWhiteSpace(bodyJson)) request.Content = CreateJsonContent(bodyJson);
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
        if (!response.IsSuccessStatusCode)
        {
            var error = Encoding.UTF8.GetString(await ReadLimitedBytesAsync(response.Content, _settings.MaxTextResponseBytes));
            throw new HttpRequestException($"RAGFlow HTTP {(int)response.StatusCode}: {error}");
        }

        var contentType = response.Content.Headers.ContentType?.MediaType ?? "application/octet-stream";
        byte[]? bufferedJson = null;
        if (contentType.Contains("json", StringComparison.OrdinalIgnoreCase))
        {
            bufferedJson = await ReadLimitedBytesAsync(response.Content, _settings.MaxTextResponseBytes);
            ValidateJsonResult(bufferedJson);
        }

        var temporaryPath = Path.Combine(parent, $".{Path.GetFileName(fullPath)}.{Guid.NewGuid():N}.tmp");
        long bytes;
        try
        {
            await using (var destination = new FileStream(temporaryPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                if (bufferedJson is not null)
                {
                    await destination.WriteAsync(bufferedJson);
                }
                else
                {
                    await using var source = await response.Content.ReadAsStreamAsync();
                    await source.CopyToAsync(destination);
                }
                bytes = destination.Length;
            }
            File.Move(temporaryPath, fullPath, overwrite);
        }
        finally
        {
            if (File.Exists(temporaryPath)) File.Delete(temporaryPath);
        }
        return new
        {
            path = fullPath,
            bytes,
            contentType = response.Content.Headers.ContentType?.ToString() ?? "application/octet-stream"
        };
    }

    private async Task<JsonElement> SendAsync(HttpMethod method, string path, object? body = null)
    {
        _settings.RequireApiKey();
        using var request = CreateRequest(method, path);
        if (body is not null) request.Content = new StringContent(JsonSerializer.Serialize(body, JsonOptions), Encoding.UTF8, "application/json");
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
        return await ReadResultAsync(response);
    }

    private async Task<JsonElement> SendJsonAsync(HttpMethod method, string path, string? bodyJson)
    {
        _settings.RequireApiKey();
        using var request = CreateRequest(method, path);
        if (!string.IsNullOrWhiteSpace(bodyJson)) request.Content = CreateJsonContent(bodyJson);
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
        return await ReadResultAsync(response);
    }

    private HttpRequestMessage CreateRequest(HttpMethod method, string path)
    {
        var request = new HttpRequestMessage(method, path.TrimStart('/'));
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _settings.ApiKey);
        return request;
    }

    private static HttpMethod ParseMethod(string method) => method.Trim().ToUpperInvariant() switch
    {
        "GET" => HttpMethod.Get,
        "HEAD" => HttpMethod.Head,
        "POST" => HttpMethod.Post,
        "PUT" => HttpMethod.Put,
        "PATCH" => HttpMethod.Patch,
        "DELETE" => HttpMethod.Delete,
        _ => throw new ArgumentException("method must be GET, HEAD, POST, PUT, PATCH, or DELETE.", nameof(method))
    };

    private static string ValidateApiPath(string relativePath)
    {
        if (string.IsNullOrWhiteSpace(relativePath)) throw new ArgumentException("relativePath is required.", nameof(relativePath));
        var path = relativePath.Trim().TrimStart('/');
        if (Uri.TryCreate(relativePath, UriKind.Absolute, out _) || !path.StartsWith("api/v1/", StringComparison.Ordinal))
            throw new ArgumentException("Only relative RAGFlow /api/v1 paths are allowed.", nameof(relativePath));
        if (path.Contains("..", StringComparison.Ordinal) || path.Contains('\\') || path.Contains('\r') || path.Contains('\n') || path.Contains('#'))
            throw new ArgumentException("relativePath contains a prohibited sequence.", nameof(relativePath));
        return path;
    }

    private static StringContent CreateJsonContent(string bodyJson)
    {
        using var _ = JsonDocument.Parse(bodyJson);
        return new StringContent(bodyJson, Encoding.UTF8, "application/json");
    }

    private async Task<JsonElement> ReadResultAsync(HttpResponseMessage response)
    {
        var mediaType = response.Content.Headers.ContentType?.MediaType ?? "";
        if (mediaType.Equals("text/event-stream", StringComparison.OrdinalIgnoreCase))
            throw new NotSupportedException("Streaming SSE responses cannot be represented as one MCP tool result. Set stream=false in the RAGFlow request body or call the RAGFlow streaming endpoint directly.");

        var bytes = await ReadLimitedBytesAsync(response.Content, _settings.MaxTextResponseBytes);
        var text = Encoding.UTF8.GetString(bytes);
        if (!response.IsSuccessStatusCode) throw new HttpRequestException($"RAGFlow HTTP {(int)response.StatusCode}: {text}");
        if (!mediaType.Contains("json", StringComparison.OrdinalIgnoreCase))
        {
            return JsonSerializer.SerializeToElement(new { contentType = mediaType, content = text });
        }
        return ValidateJsonResult(bytes);
    }

    private static JsonElement ValidateJsonResult(byte[] bytes)
    {
        using var document = JsonDocument.Parse(bytes.Length == 0 ? "{}"u8.ToArray() : bytes);
        var root = document.RootElement;
        if (root.ValueKind == JsonValueKind.Object && root.TryGetProperty("code", out var code))
        {
            var parsed = code.ValueKind == JsonValueKind.Number && code.TryGetInt32(out var numericCode)
                ? numericCode
                : code.ValueKind == JsonValueKind.String && int.TryParse(code.GetString(), out numericCode) ? numericCode : 0;
            if (parsed != 0)
            {
                var message = root.TryGetProperty("message", out var value) ? value.GetString() : "Unknown RAGFlow error";
                throw new InvalidOperationException($"RAGFlow error {parsed}: {message}");
            }
        }
        return root.Clone();
    }

    private static async Task<byte[]> ReadLimitedBytesAsync(HttpContent content, long maxBytes)
    {
        if (content.Headers.ContentLength > maxBytes)
            throw new InvalidOperationException($"RAGFlow response exceeds the configured {maxBytes} byte text limit.");

        await using var source = await content.ReadAsStreamAsync();
        using var destination = new MemoryStream();
        var buffer = new byte[81920];
        while (true)
        {
            var read = await source.ReadAsync(buffer);
            if (read == 0) break;
            if (destination.Length + read > maxBytes)
                throw new InvalidOperationException($"RAGFlow response exceeds the configured {maxBytes} byte text limit.");
            await destination.WriteAsync(buffer.AsMemory(0, read));
        }
        return destination.ToArray();
    }
}

public sealed record RagFlowHealth(
    string Status,
    bool Available,
    string RagflowBaseUrl,
    bool ApiKeyConfigured,
    bool WritesEnabled,
    bool FileWritesEnabled,
    bool McpAuthenticationEnabled,
    long MaxTextResponseBytes,
    int? HttpStatus,
    string? Error);
