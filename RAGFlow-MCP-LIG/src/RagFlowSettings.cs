public sealed record RagFlowSettings(
    string BaseUrl,
    int TimeoutMinutes,
    bool WritesEnabled,
    bool FileWritesEnabled,
    long MaxTextResponseBytes)
{
    public static RagFlowSettings Load()
    {
        var baseUrl = Environment.GetEnvironmentVariable("RAGFLOW_BASE_URL") ?? "http://127.0.0.1:42301";
        var timeout = int.TryParse(Environment.GetEnvironmentVariable("RAGFLOW_TIMEOUT_MINUTES"), out var value) ? Math.Clamp(value, 1, 1440) : 30;
        var writes = string.Equals(Environment.GetEnvironmentVariable("RAGFLOW_WRITES_ENABLED"), "true", StringComparison.OrdinalIgnoreCase);
        var fileWrites = string.Equals(Environment.GetEnvironmentVariable("RAGFLOW_FILE_WRITES_ENABLED"), "true", StringComparison.OrdinalIgnoreCase);
        var maxTextMegabytes = int.TryParse(Environment.GetEnvironmentVariable("RAGFLOW_MAX_TEXT_RESPONSE_MB"), out var maxValue) ? Math.Clamp(maxValue, 1, 64) : 4;
        return new(baseUrl, timeout, writes, fileWrites, maxTextMegabytes * 1024L * 1024L);
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
