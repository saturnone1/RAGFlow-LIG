public sealed record RagFlowSettings(
    string BaseUrl,
    string ApiKey,
    int TimeoutMinutes,
    bool WritesEnabled,
    bool FileWritesEnabled,
    long MaxTextResponseBytes,
    string McpApiKey)
{
    public static RagFlowSettings Load()
    {
        var baseUrl = Environment.GetEnvironmentVariable("RAGFLOW_BASE_URL") ?? "http://127.0.0.1:42301";
        var apiKey = Environment.GetEnvironmentVariable("RAGFLOW_API_KEY") ?? "";
        var timeout = int.TryParse(Environment.GetEnvironmentVariable("RAGFLOW_TIMEOUT_MINUTES"), out var value) ? Math.Clamp(value, 1, 1440) : 30;
        var writes = string.Equals(Environment.GetEnvironmentVariable("RAGFLOW_WRITES_ENABLED"), "true", StringComparison.OrdinalIgnoreCase);
        var fileWrites = string.Equals(Environment.GetEnvironmentVariable("RAGFLOW_FILE_WRITES_ENABLED"), "true", StringComparison.OrdinalIgnoreCase);
        var maxTextMegabytes = int.TryParse(Environment.GetEnvironmentVariable("RAGFLOW_MAX_TEXT_RESPONSE_MB"), out var maxValue) ? Math.Clamp(maxValue, 1, 64) : 4;
        var mcpApiKey = Environment.GetEnvironmentVariable("LIG_MCP_API_KEY") ?? "";
        return new(baseUrl, apiKey, timeout, writes, fileWrites, maxTextMegabytes * 1024L * 1024L, mcpApiKey);
    }

    public void RequireApiKey()
    {
        if (string.IsNullOrWhiteSpace(ApiKey)) throw new InvalidOperationException("RAGFLOW_API_KEY is required.");
    }

    public void RequireWrites()
    {
        if (!WritesEnabled) throw new InvalidOperationException("RAGFlow write tools are disabled by RAGFLOW_WRITES_ENABLED=false.");
    }

    public void RequireFileWrites()
    {
        if (!FileWritesEnabled) throw new InvalidOperationException("Local file downloads are disabled by RAGFLOW_FILE_WRITES_ENABLED=false.");
    }
}
