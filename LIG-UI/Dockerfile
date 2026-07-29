ARG NODE_IMAGE=node:22-bookworm-slim@sha256:6c74791e557ce11fc957704f6d4fe134a7bc8d6f5ca4403205b2966bd488f6b3
ARG RAGFLOW_BASE_IMAGE=infiniflow/ragflow:v0.26.4@sha256:16d24d1968ab59e2715a85d2590f1569c9539e0362344a42f3a23e8be06a655b
FROM ${NODE_IMAGE} AS web-builder

WORKDIR /build/web

COPY RAGFlow/web/package.json RAGFlow/web/package-lock.json ./
RUN npm ci --ignore-scripts

COPY RAGFlow/web/ ./
COPY RAGFlow/docs/ /build/docs/
COPY LIG-UI/scripts/apply-overlay.mjs /build/lig-ui/apply-overlay.mjs
COPY LIG-UI/scripts/verify-typecheck-baseline.mjs /build/lig-ui/verify-typecheck-baseline.mjs
COPY LIG-UI/overlay/ /build/lig-ui/overlay/

RUN node /build/lig-ui/verify-typecheck-baseline.mjs snapshot /tmp/ragflow-v0.26.4-ts-errors.json \
    && node /build/lig-ui/apply-overlay.mjs /build/web /build/lig-ui/overlay \
    && node /build/lig-ui/verify-typecheck-baseline.mjs check /tmp/ragflow-v0.26.4-ts-errors.json \
    && npx eslint \
        src/brand \
        src/components/file-upload-dialog/index.tsx \
        src/components/chunk-method-dialog/index.tsx \
        src/components/paddleocr-options-form-field.tsx \
        src/hooks/use-document-request.ts \
        src/layouts/components/mobile-menu-footer.tsx \
        src/pages/home/banner.tsx \
        src/pages/dataset/dataset/use-upload-document.ts \
        src/pages/dataset/dataset-setting/form-schema.test.ts \
        --ext .ts,.tsx --report-unused-disable-directives \
    && npx jest \
        src/brand/document-password.test.ts \
        src/pages/dataset/dataset-setting/form-schema.test.ts \
        --no-cache --runInBand --coverage=false \
    && npm run build

FROM ${RAGFLOW_BASE_IMAGE}

USER root
COPY LIG-Runtime/apply-runtime-patches.py /tmp/apply-lig-runtime-patches.py
COPY LIG-Runtime/lig_runtime/ /ragflow/lig_runtime/
RUN python3 /tmp/apply-lig-runtime-patches.py \
        /ragflow/rag/llm/embedding_model.py \
        /ragflow/deepdoc/parser/paddleocr_parser.py \
        /ragflow/rag/svr/task_executor.py \
        /ragflow/api/apps/restful_apis/document_api.py \
        /ragflow/api/apps/services/document_api_service.py \
        /ragflow/api/db/services/file_service.py \
        /ragflow/api/db/services/task_service.py \
        /ragflow/rag/flow/parser/parser.py \
        /ragflow/rag/flow/parser/pdf_chunk_metadata.py \
        /ragflow/api/apps/restful_apis/chunk_api.py \
        /ragflow/api/utils/file_utils.py \
        /ragflow/rag/svr/task_executor_refactor/chunk_builder.py \
        /ragflow/rag/svr/task_executor_refactor/task_handler.py \
        /ragflow/rag/app/naive.py \
        /ragflow/rag/app/picture.py \
        /ragflow/rag/svr/task_executor_refactor/chunk_service.py \
        /ragflow/rag/app/email.py \
    && rm /tmp/apply-lig-runtime-patches.py
RUN rm -rf /ragflow/web/dist && mkdir -p /ragflow/web/dist
COPY --from=web-builder /build/web/dist/ /ragflow/web/dist/
