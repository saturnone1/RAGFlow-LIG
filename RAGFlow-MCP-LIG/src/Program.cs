using ModelContextProtocol.Server;
using System.Security.Cryptography;
using System.Text;

var builder = WebApplication.CreateBuilder(args);
var listenUrls = Environment.GetEnvironmentVariable("ASPNETCORE_URLS") ?? "http://127.0.0.1:42206";
var settings = RagFlowSettings.Load();
if (!IsLoopbackOnly(listenUrls) && string.IsNullOrWhiteSpace(settings.McpApiKey))
    throw new InvalidOperationException("LIG_MCP_API_KEY is required when ASPNETCORE_URLS listens beyond localhost.");

builder.WebHost.UseUrls(listenUrls);
builder.Services.AddSingleton(settings);
builder.Services.AddHttpClient<RagFlowClient>((services, client) =>
{
    var settings = services.GetRequiredService<RagFlowSettings>();
    client.BaseAddress = new Uri(settings.BaseUrl.TrimEnd('/') + "/");
    client.Timeout = TimeSpan.FromMinutes(settings.TimeoutMinutes);
}).ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler { AllowAutoRedirect = false });
#pragma warning disable MCP9004
builder.Services.AddMcpServer().WithHttpTransport(options => options.EnableLegacySse = true).WithTools<RagFlowTools>();
#pragma warning restore MCP9004

var app = builder.Build();
app.Use(async (context, next) =>
{
    if (context.Request.Path == "/healthz" || string.IsNullOrWhiteSpace(settings.McpApiKey))
    {
        await next();
        return;
    }

    var authorization = context.Request.Headers.Authorization.ToString();
    const string prefix = "Bearer ";
    var supplied = authorization.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) ? authorization[prefix.Length..] : "";
    var expectedBytes = Encoding.UTF8.GetBytes(settings.McpApiKey);
    var suppliedBytes = Encoding.UTF8.GetBytes(supplied);
    if (expectedBytes.Length != suppliedBytes.Length || !CryptographicOperations.FixedTimeEquals(expectedBytes, suppliedBytes))
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        await context.Response.WriteAsJsonAsync(new { error = "A valid LIG MCP bearer token is required." });
        return;
    }
    await next();
});
app.MapGet("/healthz", async (RagFlowClient client) => Results.Ok(await client.HealthAsync()));
app.MapMcp("/mcp");
app.MapMcp("");
await app.RunAsync();

static bool IsLoopbackOnly(string urls) => urls.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).All(url =>
{
    if (!Uri.TryCreate(url, UriKind.Absolute, out var uri)) return false;
    return uri.IsLoopback || string.Equals(uri.Host, "localhost", StringComparison.OrdinalIgnoreCase);
});
