using ModelContextProtocol.Server;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls(Environment.GetEnvironmentVariable("ASPNETCORE_URLS") ?? "http://127.0.0.1:42220");
builder.Services.AddSingleton(RagFlowSettings.Load());
builder.Services.AddHttpClient<RagFlowClient>((services, client) =>
{
    var settings = services.GetRequiredService<RagFlowSettings>();
    client.BaseAddress = new Uri(settings.BaseUrl.TrimEnd('/') + "/");
    client.Timeout = TimeSpan.FromMinutes(settings.TimeoutMinutes);
});
#pragma warning disable MCP9004
builder.Services.AddMcpServer().WithHttpTransport(options => options.EnableLegacySse = true).WithTools<RagFlowTools>();
#pragma warning restore MCP9004

var app = builder.Build();
app.MapGet("/healthz", async (RagFlowClient client) => Results.Ok(await client.HealthAsync()));
app.MapMcp("/mcp");
app.MapMcp("");
await app.RunAsync();
