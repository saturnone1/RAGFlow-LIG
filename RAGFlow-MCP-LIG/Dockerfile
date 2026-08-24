FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim@sha256:3c0edbfe1549dd93fb789dc96299a40df865ad7bffefcaf38e8c05940686d641 AS build

WORKDIR /src
COPY src/RagFlowMcp.csproj ./
RUN dotnet restore RagFlowMcp.csproj
COPY src/ ./
RUN dotnet publish RagFlowMcp.csproj \
    --configuration Release \
    --no-restore \
    --output /app/publish \
    /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0-bookworm-slim@sha256:8f6a307ae32fb393a4b4bcde0a81f0ce3f0a715de0e5575df71f3030448f2dde AS runtime

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
    CMD ["curl", "--fail", "--silent", "--show-error", "http://127.0.0.1:8080/healthz"]

ENTRYPOINT ["dotnet", "LigRagFlowMcp.dll"]
