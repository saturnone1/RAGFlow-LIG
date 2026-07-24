ARG NODE_IMAGE=node:22-bookworm-slim
ARG RAGFLOW_BASE_IMAGE=infiniflow/ragflow:v0.26.4
FROM ${NODE_IMAGE} AS web-builder

WORKDIR /build/web

COPY RAGFlow/web/package.json RAGFlow/web/package-lock.json ./
RUN npm ci --ignore-scripts

COPY RAGFlow/web/ ./
COPY RAGFlow/docs/ /build/docs/
COPY LIG-UI/scripts/apply-overlay.mjs /build/lig-ui/apply-overlay.mjs
COPY LIG-UI/overlay/ /build/lig-ui/overlay/

RUN node /build/lig-ui/apply-overlay.mjs /build/web /build/lig-ui/overlay \
    && npm run build

FROM ${RAGFLOW_BASE_IMAGE}

USER root
RUN rm -rf /ragflow/web/dist && mkdir -p /ragflow/web/dist
COPY --from=web-builder /build/web/dist/ /ragflow/web/dist/
