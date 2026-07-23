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

    public async Task<object> HealthAsync()
    {
        using var response = await _http.GetAsync("api/v1/system/version");
        return new { status = response.IsSuccessStatusCode ? "ok" : "unavailable", ragflowBaseUrl = _settings.BaseUrl, apiKeyConfigured = !string.IsNullOrWhiteSpace(_settings.ApiKey), writesEnabled = _settings.WritesEnabled, httpStatus = (int)response.StatusCode };
    }

    public Task<JsonElement> GetAsync(string path) => SendAsync(HttpMethod.Get, path);
    public Task<JsonElement> PostAsync(string path, object? body = null) => SendAsync(HttpMethod.Post, path, body);
    public Task<JsonElement> PutAsync(string path, object? body = null) => SendAsync(HttpMethod.Put, path, body);
    public Task<JsonElement> PatchAsync(string path, object? body = null) => SendAsync(HttpMethod.Patch, path, body);
    public Task<JsonElement> DeleteAsync(string path, object? body = null) => SendAsync(HttpMethod.Delete, path, body);

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

    private async Task<JsonElement> SendAsync(HttpMethod method, string path, object? body = null)
    {
        _settings.RequireApiKey();
        using var request = CreateRequest(method, path);
        if (body is not null) request.Content = new StringContent(JsonSerializer.Serialize(body, JsonOptions), Encoding.UTF8, "application/json");
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
        return await ReadResultAsync(response);
    }

    private HttpRequestMessage CreateRequest(HttpMethod method, string path)
    {
        var request = new HttpRequestMessage(method, path.TrimStart('/'));
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _settings.ApiKey);
        return request;
    }

    private static async Task<JsonElement> ReadResultAsync(HttpResponseMessage response)
    {
        var text = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode) throw new HttpRequestException($"RAGFlow HTTP {(int)response.StatusCode}: {text}");
        using var document = JsonDocument.Parse(string.IsNullOrWhiteSpace(text) ? "{}" : text);
        var root = document.RootElement;
        if (root.ValueKind == JsonValueKind.Object && root.TryGetProperty("code", out var code) && code.GetInt32() != 0)
        {
            var message = root.TryGetProperty("message", out var value) ? value.GetString() : "Unknown RAGFlow error";
            throw new InvalidOperationException($"RAGFlow error {code.GetInt32()}: {message}");
        }
        return root.Clone();
    }
}
