using ModelContextProtocol.Server;

var builder = WebApplication.CreateBuilder(args);
var listenUrls = Environment.GetEnvironmentVariable("ASPNETCORE_URLS") ?? "http://127.0.0.1:42206";
var settings = RagFlowSettings.Load();

builder.WebHost.UseUrls(listenUrls);
builder.Services.AddSingleton(settings);
builder.Services.AddHttpContextAccessor();
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
    if (context.Request.Path == "/healthz")
    {
        await next();
        return;
    }

    var authorization = context.Request.Headers.Authorization.ToString();
    const string prefix = "Bearer ";
    var supplied = authorization.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) ? authorization[prefix.Length..].Trim() : "";
    if (string.IsNullOrWhiteSpace(supplied))
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        await context.Response.WriteAsJsonAsync(new { error = "A personal RAGFlow API key is required as a Bearer token." });
        return;
    }
    await next();
});
app.MapGet("/healthz", async (RagFlowClient client) =>
{
    var health = await client.HealthAsync();
    return health.Available ? Results.Ok(health) : Results.Json(health, statusCode: StatusCodes.Status503ServiceUnavailable);
});
app.MapMcp("/mcp");
app.MapMcp("");
await app.RunAsync();
