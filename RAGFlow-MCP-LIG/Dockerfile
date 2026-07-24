FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim AS build

WORKDIR /src
COPY src/RagFlowMcp.csproj ./
RUN dotnet restore RagFlowMcp.csproj
COPY src/ ./
RUN dotnet publish RagFlowMcp.csproj \
    --configuration Release \
    --no-restore \
    --output /app/publish \
    /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0-bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /app/publish ./

ENV ASPNETCORE_URLS=http://0.0.0.0:8080 \
    DOTNET_EnableDiagnostics=0 \
    RAGFLOW_WRITES_ENABLED=false \
    RAGFLOW_FILE_WRITES_ENABLED=false \
    RAGFLOW_MAX_TEXT_RESPONSE_MB=4

EXPOSE 8080
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=5 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8080/healthz || exit 1

ENTRYPOINT ["dotnet", "LigRagFlowMcp.dll"]
