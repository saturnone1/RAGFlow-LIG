public sealed record RagFlowSettings(string BaseUrl, string ApiKey, int TimeoutMinutes, bool WritesEnabled)
{
    public static RagFlowSettings Load()
    {
        var baseUrl = Environment.GetEnvironmentVariable("RAGFLOW_BASE_URL") ?? "http://127.0.0.1:9380";
        var apiKey = Environment.GetEnvironmentVariable("RAGFLOW_API_KEY") ?? "";
        var timeout = int.TryParse(Environment.GetEnvironmentVariable("RAGFLOW_TIMEOUT_MINUTES"), out var value) ? Math.Clamp(value, 1, 1440) : 30;
        var writes = !string.Equals(Environment.GetEnvironmentVariable("RAGFLOW_WRITES_ENABLED"), "false", StringComparison.OrdinalIgnoreCase);
        return new(baseUrl, apiKey, timeout, writes);
    }

    public void RequireApiKey()
    {
        if (string.IsNullOrWhiteSpace(ApiKey)) throw new InvalidOperationException("RAGFLOW_API_KEY is required.");
    }

    public void RequireWrites()
    {
        if (!WritesEnabled) throw new InvalidOperationException("RAGFlow write tools are disabled by RAGFLOW_WRITES_ENABLED=false.");
    }
}
