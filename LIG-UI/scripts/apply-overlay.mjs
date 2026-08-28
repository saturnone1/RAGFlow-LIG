import { cpSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';

const [webRoot, overlayRoot] = process.argv.slice(2);

if (!webRoot || !overlayRoot) {
  throw new Error('Usage: node apply-overlay.mjs <web-root> <overlay-root>');
}

const expectedHashes = {
  'index.html': 'ec8b1e543133a6ef043a27d4ac092947d8d2114856cf8b55d0178183f3177ead',
  'src/app.tsx': '934eb8ed06386dfece50770ad9f0c1cf47b4c4b4034c5d7b4c0c173bedeb9a6a',
  'src/main.tsx': '4e1059ccbf162543782c92f38bc7dd8367f548b289dff45badafd2a36d0639b0',
  'src/layouts/components/header.tsx': '64a55c4f420cc206429296c087dfa91bdce38660acb8931c838af6449307ebc6',
  'src/layouts/components/global-navbar.tsx': '6fd4b78b83608488c12b36d5506b54d7bbdf74ec48ceca5e29f03cce23eb6cdd',
  'src/layouts/components/mobile-menu-footer.tsx': '48b9e80c4c18832daf3c96c1410dfddce64c3063ac81a96a49895b98bc063d98',
  'src/pages/login-next/index.tsx': '732de089c1abeb011d135db20b6a6f72a0bddb2af14d61b729220221f923417b',
  'src/pages/home/banner.tsx': 'f066aef325bde293600ca768549e73adae709f717e5e62088265bb74e1298566',
  'src/pages/admin/layouts/navigation-layout.tsx': 'd5355804d831d0d8bf93da1bca4cabfb74ef818064c3349b262d828b2a8eb6df',
  'src/locales/en.ts': 'b4780d29761defb95869962e7ff270a09b3b7ccc81f6130b9ebf5328454101b2',
  'src/locales/ko.ts': 'e2fcf6fd6d23ade3700acf15aa670dd0bcafb31e5586ef0dc175e7e71a3f1d3f',
  'src/components/api-service/chat-overview-modal/backend-service-api.tsx': '6d5c6a24167883269be157c01f3a36fe3324d1c43e87f242a23aa9a37eec752d',
  'src/components/embed-dialog/index.tsx': '47aec9038666136f4536c0f60ad2b4685dd9510ed7eec0a0e9e7e165b05cf741',
  'src/constants/agent.tsx': 'cc248cba0aa8d9ef309a48097ad24cab5da828658f9a896ba1810f2004e2f67c',
  'src/pages/dataset/dataset-setting/form-schema.ts': '42414b182a33d7ec500229bf3ee971a5c2ccedf247b5312b39b379d56e5f8df2',
  'src/pages/dataset/dataset-setting/saving-button.tsx': '07b515ed2b8bf3b1c32c3a8e3d431e5971bb8722aca21da867334da629f7fef4',
  'src/components/file-upload-dialog/index.tsx': 'c502c71104ff5eeceb560b20874d14ebc9ef431c769c2fafa0501db4f605625c',
  'src/pages/dataset/dataset/use-upload-document.ts': '58bd2fc4439f3d47abaa8ad123f79d2a64b3e3bd5415e13d50103dfd41ca0f0f',
  'src/hooks/use-document-request.ts': '2033e111411218c3299412ffd65ce2d17c082b670bd263e5ca1ed99e754e1bfc',
  'src/components/chunk-method-dialog/index.tsx': '0dec00d6c24a26a9594414668b4695b4a2a357767c2f3bd4f19a0a4b8c707463',
  'src/interfaces/database/document.ts': 'ab4093f0eedadc34063f100c27f362ff4cb4ba87a4be84c91ff973902ec85736',
  'src/interfaces/request/document.ts': '99cff0a70f4d815e6f7bcbae3711f81d7704b8f96bd8775c8e1f644aff345cc0',
  'src/pages/dataset/process-log-modal.tsx': 'd140832272a8d204e8da8e70ec1f05949f901d3795ef3fda57a9000b01552cc6',
  'src/hooks/use-knowledge-request.ts': '5a43702ec53f713e86f1f087ee638d2fd42c8acad0ae17cf1a881b6c41487fdc',
  'src/hooks/use-llm-request.tsx': 'da875698d419f92f02c86ee6e62e1e016928a1c1c8db5e2a5c51cc5d328a3e1c',
  'src/pages/user-setting/setting-model/modal/provider-modal/field-config/provider-config-map.ts':
    'abfef8b4daf93d05306c86ecb856eb49c2944ce25378fa539a691c32e5644f8e',
};

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

for (const [relativePath, expected] of Object.entries(expectedHashes)) {
  const actual = sha256(join(webRoot, relativePath));
  if (actual !== expected) {
    throw new Error(
      `Unsupported RAGFlow web source: ${relativePath}\nexpected ${expected}\nactual   ${actual}`,
    );
  }
}

function read(relativePath) {
  return readFileSync(join(webRoot, relativePath), 'utf8').replace(/\r\n/g, '\n');
}

function write(relativePath, content) {
  writeFileSync(join(webRoot, relativePath), content, 'utf8');
}

function replaceOnce(content, before, after, label) {
  const first = content.indexOf(before);
  if (first < 0 || content.indexOf(before, first + before.length) >= 0) {
    throw new Error(`Expected exactly one match while applying ${label}`);
  }
  return content.slice(0, first) + after + content.slice(first + before.length);
}

function replaceSuffix(content, before, after, label) {
  const trailingNewline = content.endsWith('\n') ? '\n' : '';
  const body = trailingNewline ? content.slice(0, -1) : content;
  if (!body.endsWith(before)) {
    throw new Error(`Expected suffix while applying ${label}`);
  }
  return body.slice(0, -before.length) + after + trailingNewline;
}

let content = read('src/main.tsx');
content = replaceOnce(
  content,
  "import './global.less';",
  "import './global.less';\nimport './brand/brand.css';",
  'brand stylesheet import',
);
write('src/main.tsx', content);

content = read('src/app.tsx');
content = replaceOnce(
  content,
  'defaultTheme={ThemeEnum.Dark}',
  'defaultTheme={ThemeEnum.Light}',
  'light default theme',
);
write('src/app.tsx', content);

content = read('src/pages/dataset/process-log-modal.tsx');
content = replaceOnce(
  content,
  'bg-bg-card rounded-lg h-fit max-h-[350px] overflow-y-auto',
  'bg-bg-card rounded-lg h-fit max-h-[65vh] overflow-y-auto',
  'expanded process log viewport',
);
write('src/pages/dataset/process-log-modal.tsx', content);

content = read('src/hooks/use-knowledge-request.ts');
content = replaceOnce(
  content,
  `          queryClient.invalidateQueries({
            queryKey: [KnowledgeApiAction.FetchKnowledgeListByPage],
          });
        } else {
          queryClient.invalidateQueries({ queryKey: ['fetchKnowledgeDetail'] });`,
  `          await queryClient.invalidateQueries({
            queryKey: [KnowledgeApiAction.FetchKnowledgeListByPage],
          });
        } else {
          await queryClient.invalidateQueries({
            queryKey: ['fetchKnowledgeDetail'],
          });`,
  'await dataset configuration refresh after save',
);
content = replaceOnce(
  content,
  `      if (data.code === 0) {
        message.success(i18n.t(\`message.updated\`));
        if (shouldFetchList) {`,
  `      if (data.code === 0) {
        if (shouldFetchList) {`,
  'delay dataset saved message until refresh',
);
content = replaceOnce(
  content,
  `          await queryClient.invalidateQueries({
            queryKey: ['fetchKnowledgeDetail'],
          });
        }
      }
      return data;`,
  `          await queryClient.invalidateQueries({
            queryKey: ['fetchKnowledgeDetail'],
          });
        }
        message.success(i18n.t(\`message.updated\`));
      }
      return data;`,
  'show dataset saved message after refresh',
);
write('src/hooks/use-knowledge-request.ts', content);

content = read('src/pages/dataset/dataset-setting/saving-button.tsx');
content = replaceOnce(
  content,
  "import { useMemo } from 'react';",
  "import { useMemo, useState } from 'react';\nimport { useHasParsedDocument } from './hooks';",
  'dataset save status imports',
);
content = replaceOnce(
  content,
  `  const { t } = useTranslation();

  return (
    <ButtonLoading
      loading={submitLoading}
      data-testid="ds-settings-page-save-btn"`,
  `  const { t } = useTranslation();
  const hasParsedDocument = useHasParsedDocument();
  const [saveOutcome, setSaveOutcome] = useState<'applied' | 'reprocess' | null>(null);
  const dirtyFields = form.formState.dirtyFields;
  const hasUnsavedChanges = form.formState.isDirty;
  const requiresReprocessing =
    hasParsedDocument &&
    Boolean(
      dirtyFields.embedding_model ||
        dirtyFields.chunk_method ||
        dirtyFields.pipeline_id ||
        dirtyFields.parser_config,
    );
  const layoutRecognize = String(
    form.watch('parser_config.layout_recognize') ?? '',
  ).toLowerCase();
  const usesPaddleOcr = layoutRecognize.startsWith('paddleocr');

  return (
    <>
      <div className="mr-auto text-xs text-text-secondary">
        {!hasUnsavedChanges && saveOutcome === 'applied' &&
          t('knowledgeConfiguration.ligSettingsApplied')}
        {!hasUnsavedChanges && saveOutcome === 'reprocess' &&
          t('knowledgeConfiguration.ligReprocessRequired')}
        {hasUnsavedChanges && requiresReprocessing &&
          t('knowledgeConfiguration.ligWillRequireReprocess')}
        {usesPaddleOcr && (
          <span className="ml-2">
            {t('knowledgeConfiguration.ligPaddleServiceRequired')}
          </span>
        )}
      </div>
      <ButtonLoading
        loading={submitLoading}
        data-testid="ds-settings-page-save-btn"`,
  'dataset save status panel',
);
content = replaceOnce(
  content,
  '                await saveKnowledgeConfiguration({',
  '                const result = await saveKnowledgeConfiguration({',
  'capture dataset save result',
);
content = replaceOnce(
  content,
  `                  },
                });
              })();`,
  `                  },
                });
                if (result.code === 0) {
                  setSaveOutcome(requiresReprocessing ? 'reprocess' : 'applied');
                }
              })();`,
  'show effective dataset save result',
);
content = replaceSuffix(
  content,
  `      {t('knowledgeConfiguration.save')}
    </ButtonLoading>
  );
}`,
  `      {t('knowledgeConfiguration.save')}
      </ButtonLoading>
    </>
  );
}`,
  'close dataset save status panel',
);
write('src/pages/dataset/dataset-setting/saving-button.tsx', content);

content = read('src/hooks/use-llm-request.tsx');
content = replaceOnce(
  content,
  `        queryClient.invalidateQueries({
          queryKey: LlmKeys.instanceModels(
            params.provider_name,
            params.instance_name,
          ),
        });
      }
      return data;`,
  `        queryClient.invalidateQueries({
          queryKey: LlmKeys.instanceModels(
            params.provider_name,
            params.instance_name,
          ),
        });
        queryClient.invalidateQueries({
          queryKey: LlmKeys.allModels(),
        });
      }
      return data;`,
  'refresh all model selectors after model status change',
);
write('src/hooks/use-llm-request.tsx', content);

content = read(
  'src/pages/user-setting/setting-model/modal/provider-modal/field-config/provider-config-map.ts',
);
const paddleProviderStart = content.indexOf('  // ============ PaddleOCR ============');
const paddleProviderEnd = content.indexOf(
  '  // ============ MinerU ============',
  paddleProviderStart,
);
if (paddleProviderStart < 0 || paddleProviderEnd < 0) {
  throw new Error('PaddleOCR provider configuration block was not found');
}
let paddleProvider = content.slice(paddleProviderStart, paddleProviderEnd);
paddleProvider = replaceOnce(
  paddleProvider,
  `      },
    ],
    verifyTransform:`,
  `      },
      {
        name: 'paddleocr_api_mode',
        label: 'paddleocrApiMode',
        type: FormFieldType.Select,
        required: false,
        defaultValue: 'auto',
        options: [
          { label: 'Auto', value: 'auto' },
          { label: 'RAGFlow Job API', value: 'job' },
          { label: 'PaddleX Image API', value: 'direct-image' },
        ],
      },
      {
        name: 'paddleocr_direct_workers',
        label: 'paddleocrDirectWorkers',
        type: FormFieldType.Number,
        required: false,
        defaultValue: 8,
        validation: { min: 1, message: 'paddleocrDirectWorkersMessage' },
      },
      {
        name: 'paddleocr_direct_render_dpi',
        label: 'paddleocrDirectRenderDpi',
        type: FormFieldType.Number,
        required: false,
        defaultValue: 144,
        validation: { min: 1, message: 'paddleocrDirectRenderDpiMessage' },
      },
    ],
    verifyTransform:`,
  'PaddleOCR provider execution fields',
);
const algorithmTransform = `      if (values.paddleocr_algorithm)
        cfg.paddleocr_algorithm = values.paddleocr_algorithm;`;
if (paddleProvider.split(algorithmTransform).length - 1 !== 2) {
  throw new Error('Expected PaddleOCR verify and submit transforms');
}
paddleProvider = paddleProvider.replaceAll(
  algorithmTransform,
  `${algorithmTransform}
      if (values.paddleocr_api_mode)
        cfg.paddleocr_api_mode = values.paddleocr_api_mode;
      if (values.paddleocr_direct_workers)
        cfg.paddleocr_direct_workers = Number(values.paddleocr_direct_workers);
      if (values.paddleocr_direct_render_dpi)
        cfg.paddleocr_direct_render_dpi = Number(values.paddleocr_direct_render_dpi);`,
);
content =
  content.slice(0, paddleProviderStart) +
  paddleProvider +
  content.slice(paddleProviderEnd);
write(
  'src/pages/user-setting/setting-model/modal/provider-modal/field-config/provider-config-map.ts',
  content,
);

content = read('index.html');
content = replaceOnce(
  content,
  '<link rel="icon" type="image/svg+xml" href="/logo.svg" />',
  '<link rel="icon" type="image/png" href="/brand/lig-signature-blue.png" />\n    <meta name="theme-color" content="#002f6d" />',
  'favicon',
);
content = replaceOnce(content, '<title>RAGFlow</title>', '<title>LIG AI Knowledge Hub</title>', 'document title');
write('index.html', content);

content = read('src/layouts/components/header.tsx');
content = content.replace("import { IconFontFill } from '@/components/icon-font';\n", '');
content = content.replace('  LucideCircleHelp,\n', '');
content = "import { BrandHeaderLogo } from '@/brand/brand-logo';\n" + content;
content = replaceOnce(
  content,
  `className="flex size-10 shrink-0 items-center justify-center"
            >
              <img src={'/logo.svg'} alt="RAGFlow logo" className="size-10" />`,
  `className="flex shrink-0 items-center"
            >
              <BrandHeaderLogo />`,
  'header logo',
);
content = replaceOnce(
  content,
  `          {!isCompact && (
            <>
              <a
                className="inline-flex p-2 text-text-secondary hover:text-text-primary focus-visible:text-text-primary"
                target="_blank"
                href="https://discord.com/invite/NjYzJD3GM3"
                rel="noreferrer noopener"
              >
                <IconFontFill name="a-DiscordIconSVGVectorIcon" />
              </a>

              <a
                className="inline-flex p-2 text-text-secondary hover:text-text-primary focus-visible:text-text-primary"
                target="_blank"
                href="https://github.com/infiniflow/ragflow"
                rel="noreferrer noopener"
              >
                <IconFontFill name="GitHub" />
              </a>
            </>
          )}

`,
  '',
  'community links',
);
content = replaceOnce(
  content,
  `              <Button
                asLink
                variant="ghost"
                size="icon"
                className="size-8"
                to="https://ragflow.io/docs/dev/category/user-guides"
                target="_blank"
                rel="noreferrer noopener"
              >
                <LucideCircleHelp className="size-[1em]" />
              </Button>

`,
  '',
  'external help link',
);
content = content.replace(
  `          <a className="inline-flex p-2">
            <IconFontFill name="a-DiscordIconSVGVectorIcon" />
          </a>
          <a className="inline-flex p-2">
            <IconFontFill name="GitHub" />
          </a>
`,
  '',
);
content = content.replace(
  `          <Button variant="ghost" size="icon" className="size-8">
            <LucideCircleHelp className="size-[1em]" />
          </Button>
`,
  '',
);
write('src/layouts/components/header.tsx', content);

content = read('src/layouts/components/global-navbar.tsx');
content = "import { BrandSignature } from '@/brand/brand-logo';\n" + content;
content = replaceOnce(
  content,
  '<img src="/logo.svg" alt="RAGFlow logo" className="size-9" />',
  '<BrandSignature className="w-40 lig-logo-light" />\n          <BrandSignature inverse className="w-40 lig-logo-dark" />',
  'mobile navigation logo',
);
write('src/layouts/components/global-navbar.tsx', content);

content = read('src/pages/login-next/index.tsx');
content = content.replace("import Spotlight from '@/components/spotlight';\n", '');
content = content.replace("import { BgSvg } from './bg';\n", '');
content = "import { BrandLoginShell } from '@/brand/brand-login-shell';\n" + content;
content = replaceOnce(
  content,
  'className=" w-full max-w-[540px] bg-bg-component backdrop-blur-sm rounded-2xl shadow-xl pt-14 pl-10 pr-10 pb-2 border border-border-button "',
  'className="lig-login-card w-full max-w-[540px] bg-bg-component pt-14 pl-10 pr-10 pb-2"',
  'login card style',
);
content = replaceOnce(
  content,
  'className="bg-metallic-gradient border-b-[#00BEB4] border-b-2 hover:bg-metallic-gradient hover:border-b-[#02bcdd] w-full my-8"',
  'className="lig-primary-button w-full my-8"',
  'login primary button',
);
content = replaceOnce(
  content,
  `    } catch (errorInfo) {
      console.log('Failed:', errorInfo);
    }`,
  `    } catch {
      // Error feedback is handled by the authentication request hooks.
    }`,
  'login console cleanup',
);
const loginReturnStart = content.indexOf('  return (\n    <>\n      <Spotlight', content.indexOf('const Login ='));
const loginReturnEnd = content.indexOf('\n  );\n};\n\nexport default Login;', loginReturnStart);
if (loginReturnStart < 0 || loginReturnEnd < 0) {
  throw new Error('Unable to locate Login return block');
}
const loginReturn = `  return (
    <BrandLoginShell>
      <FlipCard3D isLoginPage={isLoginPage}>
        <LoginFormContent
          isLoginPage={isLoginPage}
          title={title}
          form={form}
          loading={loading}
          onCheck={onCheck}
          changeTitle={changeTitle}
          registerEnabled={registerEnabled}
          channels={channels || []}
          handleLoginWithChannel={handleLoginWithChannel}
          t={t}
          disablePasswordLogin={!!config?.disablePasswordLogin}
        />
      </FlipCard3D>
    </BrandLoginShell>`;
content = content.slice(0, loginReturnStart) + loginReturn + content.slice(loginReturnEnd);
write('src/pages/login-next/index.tsx', content);

content = read('src/pages/admin/layouts/navigation-layout.tsx');
content = replaceOnce(content, '              {version}', '              Based on RAGFlow {version}', 'admin attribution');
write('src/pages/admin/layouts/navigation-layout.tsx', content);

for (const localePath of ['src/locales/en.ts', 'src/locales/ko.ts']) {
  content = read(localePath).replaceAll('RAGFlow', 'LIG AI Knowledge Hub');
  write(localePath, content);
}

content = read('src/components/api-service/chat-overview-modal/backend-service-api.tsx');
content = replaceOnce(content, '<CardTitle>RAGFlow API</CardTitle>', '<CardTitle>LIG AI Knowledge Hub API</CardTitle>', 'API card title');
write('src/components/api-service/chat-overview-modal/backend-service-api.tsx', content);

content = read('src/components/embed-dialog/index.tsx');
content = replaceOnce(content, 'placeholder="Powered by RAGFlow"', 'placeholder="LIG AI Knowledge Hub"', 'embed branding placeholder');
content = replaceOnce(content, 'placeholder="https://ragflow.io"', 'placeholder="https://"', 'embed website placeholder');
write('src/components/embed-dialog/index.tsx', content);

content = read('src/constants/agent.tsx');
content = replaceOnce(
  content,
  "https://github.com/infiniflow/ragflow",
  'https://example.internal/api',
  'agent code template URL',
);
write('src/constants/agent.tsx', content);

content = read('src/pages/dataset/dataset-setting/form-schema.ts');
content = replaceOnce(
  content,
  "table_column_mode: z.enum(['auto', 'manual']).optional(),",
  "table_column_mode: z.enum(['auto', 'manual']).nullish(),",
  'nullable table column mode',
);
content = replaceOnce(
  content,
  `        table_column_roles: z
          .record(
            z
              .enum(['indexing', 'metadata', 'both', 'vectorize'])
              .transform((role) => (role === 'vectorize' ? 'indexing' : role)),
          )
          .optional(),`,
  `        table_column_roles: z
          .record(
            z
              .enum(['indexing', 'metadata', 'both', 'vectorize'])
              .transform((role) => (role === 'vectorize' ? 'indexing' : role)),
          )
          .nullish(),`,
  'nullable table column roles',
);
content = replaceOnce(
  content,
  'table_column_names: z.array(z.string()).optional(),',
  'table_column_names: z.array(z.string()).nullish(),',
  'nullable table column names',
);
write('src/pages/dataset/dataset-setting/form-schema.ts', content);

content = read('src/components/file-upload-dialog/index.tsx');
content =
  "import { documentPasswordsSchema, getUploadFile, getUploadFilePasswordKey, supportsDocumentPassword } from '@/brand/document-password';\n" +
  content;
content = replaceOnce(
  content,
  "import { Switch } from '../ui/switch';",
  "import { Switch } from '../ui/switch';\nimport { Input } from '../ui/input';",
  'document password upload input import',
);
content = replaceOnce(
  content,
  "    tableColumnMode: z.enum(['auto', 'manual']).optional(),",
  "    documentPasswords: documentPasswordsSchema,\n    tableColumnMode: z.enum(['auto', 'manual']).optional(),",
  'document password upload schema',
);
content = replaceOnce(
  content,
  "      fileList: [],\n      tableColumnMode: 'auto',",
  "      fileList: [],\n      documentPasswords: {},\n      tableColumnMode: 'auto',",
  'document password upload defaults',
);
content = replaceOnce(
  content,
  "  const [extractedColumns, setExtractedColumns] = useState<string[]>([]);",
  "  const selectedFiles = form.watch('fileList');\n  const passwordDocuments = selectedFiles.filter(supportsDocumentPassword);\n\n  const [extractedColumns, setExtractedColumns] = useState<string[]>([]);",
  'selected password-capable upload files',
);
content = replaceOnce(
  content,
  `        </RAGFlowFormItem>

        {showColumnConfig && (`,
  `        </RAGFlowFormItem>

        {passwordDocuments.length > 0 && (
          <div className="space-y-3 rounded-md border p-3">
            <div>
              <Label className="text-sm font-medium">
                {t('fileManager.documentPasswords')}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t('fileManager.documentPasswordsTip')}
              </p>
            </div>
            {passwordDocuments.map((value) => {
              const file = getUploadFile(value);
              const passwordKey = getUploadFilePasswordKey(value);
              return (
                <RAGFlowFormItem
                  key={passwordKey}
                  name={\`documentPasswords.\${passwordKey}\`}
                  label={file.name}
                >
                  {(field) => (
                    <Input
                      {...field}
                      value={field.value || ''}
                      type="password"
                      autoComplete="new-password"
                      placeholder={t('fileManager.documentPasswordPlaceholder')}
                    />
                  )}
                </RAGFlowFormItem>
              );
            })}
          </div>
        )}

        {showColumnConfig && (`,
  'per-file document password inputs',
);
write('src/components/file-upload-dialog/index.tsx', content);

content = read('src/pages/dataset/dataset/use-upload-document.ts');
content = "import message from '@/components/ui/message';\n" + content;
content = replaceOnce(
  content,
  "      tableColumnRoles,\n    }: UploadFormSchemaType) => {",
  "      tableColumnRoles,\n      documentPasswords,\n    }: UploadFormSchemaType) => {",
  'document passwords upload form value',
);
content = replaceOnce(
  content,
  '        const ret = await uploadDocument(fileList as File[], parserConfig);',
  '        const ret = await uploadDocument(fileList, parserConfig, documentPasswords);',
  'submit document passwords',
);
content = replaceOnce(
  content,
  `        if (!isSuccess && !isPartialSuccess) {
          return;
        }`,
  `        if (!isSuccess && !isPartialSuccess) {
          message.error(ret?.message || 'The selected chunk method cannot process this file.');
          return;
        }`,
  'show actionable upload compatibility error',
);
content = replaceOnce(
  content,
  `        if (count !== fileList.length) {
          hideDocumentUploadModal();
          return 0;
        }

        return ret?.code;`,
  `        if (count !== fileList.length) {
          hideDocumentUploadModal();
          message.error(ret?.message || 'Some files could not be processed.');
          return 0;
        }

        message.error(ret?.message || 'The selected chunk method cannot process these files.');
        return ret?.code;`,
  'show partial and complete upload failures',
);
write('src/pages/dataset/dataset/use-upload-document.ts', content);

content = read('src/hooks/use-document-request.ts');
content =
  "import { getUploadFile, getUploadFilePasswordKey, type UploadFileValue } from '@/brand/document-password';\n" +
  content;
content = replaceOnce(
  content,
  '{ fileList: File[]; parserConfig?: Record<string, any> }',
  '{ fileList: UploadFileValue[]; parserConfig?: Record<string, any>; documentPasswords?: Record<string, string> }',
  'upload mutation document password type',
);
content = replaceOnce(
  content,
  'mutationFn: async ({ fileList, parserConfig }) => {',
  'mutationFn: async ({ fileList, parserConfig, documentPasswords }) => {',
  'upload mutation document passwords',
);
content = replaceOnce(
  content,
  "      fileList.forEach((file: any) => {\n        formData.append('file', file);\n      });",
  "      fileList.forEach((file) => {\n        formData.append('file', getUploadFile(file));\n      });",
  'unwrap folder upload file values',
);
content = replaceOnce(
  content,
  "      if (parserConfig) {\n        formData.append('parser_config', JSON.stringify(parserConfig));\n      }",
  "      if (parserConfig) {\n        formData.append('parser_config', JSON.stringify(parserConfig));\n      }\n      if (documentPasswords) {\n        const passwords = fileList.map(\n          (file) => documentPasswords[getUploadFilePasswordKey(file)] || null,\n        );\n        formData.append('document_passwords', JSON.stringify(passwords));\n      }",
  'upload document password form data',
);
content = replaceOnce(
  content,
  "    (fileList: File[], parserConfig?: Record<string, any>) =>\n      mutateAsync({ fileList, parserConfig }),",
  "    (\n      fileList: UploadFileValue[],\n      parserConfig?: Record<string, any>,\n      documentPasswords?: Record<string, string>,\n    ) => mutateAsync({ fileList, parserConfig, documentPasswords }),",
  'upload callback document password argument',
);
write('src/hooks/use-document-request.ts', content);

content = read('src/interfaces/database/document.ts');
content = replaceOnce(
  content,
  '  enable_metadata?: boolean;\n}',
  '  enable_metadata?: boolean;\n  document_password_configured?: boolean;\n  document_password?: string;\n  clear_document_password?: boolean;\n}',
  'document password status',
);
write('src/interfaces/database/document.ts', content);

content = read('src/interfaces/request/document.ts');
content = replaceOnce(
  content,
  '  enable_metadata?: boolean;\n}',
  '  enable_metadata?: boolean;\n  document_password?: string | null;\n  clear_document_password?: boolean;\n}',
  'document password update request',
);
write('src/interfaces/request/document.ts', content);

content = read('src/components/chunk-method-dialog/index.tsx');
content =
  "import { documentPasswordSchema, supportsPasswordExtension } from '@/brand/document-password';\n" +
  content;
content = replaceOnce(
  content,
  "        task_page_size: z.coerce.number().optional(),",
  "        task_page_size: z.coerce.number().optional(),\n        document_password: documentPasswordSchema.optional(),\n        clear_document_password: z.boolean().optional(),",
  'document password form schema',
);
content = replaceOnce(
  content,
  '    const parserConfig = data.parser_config;',
  `    const {
      document_password: documentPassword,
      clear_document_password: clearDocumentPassword,
      ...parserConfig
    } = data.parser_config;`,
  'extract document password update',
);
content = replaceOnce(
  content,
  "        pages: parserConfig?.pages?.map((x: any) => [x.from, x.to]) ?? [],",
  "        pages: parserConfig?.pages?.map((x: any) => [x.from, x.to]) ?? [],\n        ...(clearDocumentPassword\n          ? { document_password: null, clear_document_password: true }\n          : documentPassword\n            ? { document_password: documentPassword }\n            : {}),",
  'submit changed document password',
);
content = replaceOnce(
  content,
  "          ...omit(parserConfig, 'pages'),",
  "          ...omit(parserConfig, ['pages', 'document_password_configured']),\n          document_password: '',\n          clear_document_password: false,",
  'reset private document password fields',
);
content = replaceOnce(
  content,
  `              {showPages && parseType === ParseType.BuiltIn && (
                <DynamicPageRange />
              )}`,
  `              {supportsPasswordExtension(documentExtension) && (
                <div className="space-y-3 rounded-md border p-3">
                  <FormField
                    control={form.control}
                    name="parser_config.document_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('fileManager.documentPassword')}</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            value={field.value || ''}
                            type="password"
                            autoComplete="new-password"
                            disabled={form.watch(
                              'parser_config.clear_document_password',
                            )}
                            placeholder={
                              parserConfig?.document_password_configured
                                ? t('fileManager.documentPasswordKeepPlaceholder')
                                : t('fileManager.documentPasswordPlaceholder')
                            }
                          />
                        </FormControl>
                        <p className="text-sm text-muted-foreground">
                          {t('fileManager.documentPasswordUpdateTip')}
                        </p>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  {parserConfig?.document_password_configured && (
                    <FormField
                      control={form.control}
                      name="parser_config.clear_document_password"
                      render={({ field }) => (
                        <FormItem className="flex items-center justify-between gap-4">
                          <FormLabel>{t('fileManager.documentPasswordClear')}</FormLabel>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormItem>
                      )}
                    />
                  )}
                </div>
              )}

              {showPages && parseType === ParseType.BuiltIn && (
                <DynamicPageRange />
              )}`,
  'document password settings',
);
content = replaceOnce(
  content,
  "import { Input } from '../ui/input';",
  "import { Input } from '../ui/input';\nimport { Switch } from '../ui/switch';",
  'document password clear switch',
);
write('src/components/chunk-method-dialog/index.tsx', content);

for (const [localePath, values] of [
  ['src/locales/en.ts', {
    label: 'Document passwords',
    tip: 'Enter a file-open password for each protected PDF, Office, HWP, or HWPX document. Unprotected files can be left blank.',
    password: 'Document password',
    placeholder: 'Enter the file-open password',
    keep: 'Leave blank to keep the saved password',
    update: 'Save a new password here, then run the document again. The password is never returned by the API.',
    clear: 'Remove the saved document password',
    paddleApiMode: 'PaddleOCR API mode',
    paddleWorkers: 'Concurrent image requests',
    paddleWorkersMessage: 'Enter at least 1 concurrent image request',
    paddleDpi: 'PDF image resolution (DPI)',
    paddleDpiMessage: 'Enter a positive PDF image resolution',
    settingsApplied: 'Saved and applied to all workers.',
    reprocessRequired: 'Saved. Reprocess existing documents to apply vector or parser changes.',
    willRequireReprocess: 'Existing documents will require reprocessing.',
    paddleServiceRequired: 'The selected PaddleOCR service must be running.',
  }],
  ['src/locales/ko.ts', {
    label: '문서 비밀번호',
    tip: '암호가 설정된 PDF, Office, HWP, HWPX마다 파일 열기 비밀번호를 입력하세요. 암호가 없는 파일은 비워 두면 됩니다.',
    password: '문서 비밀번호',
    placeholder: '파일 열기 비밀번호 입력',
    keep: '비워 두면 저장된 비밀번호를 유지합니다',
    update: '새 비밀번호를 저장한 뒤 문서를 다시 실행하세요. 비밀번호는 API 응답에 노출되지 않습니다.',
    clear: '저장된 문서 비밀번호 제거',
    paddleApiMode: 'PaddleOCR API 방식',
    paddleWorkers: '이미지 API 동시 요청',
    paddleWorkersMessage: '이미지 API 동시 요청 수를 1 이상 입력하세요',
    paddleDpi: 'PDF 이미지 해상도(DPI)',
    paddleDpiMessage: 'PDF 이미지 해상도를 1 이상 입력하세요',
    settingsApplied: '저장되어 모든 worker에 반영됐습니다.',
    reprocessRequired: '저장됐습니다. 벡터·파서 변경은 기존 문서를 다시 처리해야 적용됩니다.',
    willRequireReprocess: '기존 문서는 저장 후 재처리가 필요합니다.',
    paddleServiceRequired: '선택한 PaddleOCR 서비스가 실행 중이어야 합니다.',
  }],
]) {
  content = read(localePath);
  content = replaceOnce(
    content,
    "      parseOnCreation: " + (localePath.endsWith('/ko.ts') ? "'생성 시 파싱'," : "'Parse on creation',"),
    "      parseOnCreation: " + (localePath.endsWith('/ko.ts') ? "'생성 시 파싱'," : "'Parse on creation',") +
      `\n      documentPasswords: '${values.label}',\n      documentPasswordsTip: '${values.tip}',\n      documentPassword: '${values.password}',\n      documentPasswordPlaceholder: '${values.placeholder}',\n      documentPasswordKeepPlaceholder: '${values.keep}',\n      documentPasswordUpdateTip: '${values.update}',\n      documentPasswordClear: '${values.clear}',\n      ligSettingsApplied: '${values.settingsApplied}',\n      ligReprocessRequired: '${values.reprocessRequired}',\n      ligWillRequireReprocess: '${values.willRequireReprocess}',\n      ligPaddleServiceRequired: '${values.paddleServiceRequired}',`,
    `document password ${localePath} locale`,
  );
  content = replaceOnce(
    content,
    localePath.endsWith('/ko.ts')
      ? "      paddleocrAlgorithmMessage: 'PaddleOCR 알고리즘을 선택해 주세요',"
      : "      paddleocrAlgorithmMessage: 'Please select a PaddleOCR algorithm',",
    (localePath.endsWith('/ko.ts')
      ? "      paddleocrAlgorithmMessage: 'PaddleOCR 알고리즘을 선택해 주세요',"
      : "      paddleocrAlgorithmMessage: 'Please select a PaddleOCR algorithm',") +
      `\n      paddleocrApiMode: '${values.paddleApiMode}',\n      paddleocrDirectWorkers: '${values.paddleWorkers}',\n      paddleocrDirectWorkersMessage: '${values.paddleWorkersMessage}',\n      paddleocrDirectRenderDpi: '${values.paddleDpi}',\n      paddleocrDirectRenderDpiMessage: '${values.paddleDpiMessage}',`,
    `PaddleOCR execution ${localePath} locale`,
  );
  write(localePath, content);
}

cpSync(overlayRoot, webRoot, { recursive: true, force: true });

console.log('LIG AI Knowledge Hub overlay applied successfully.');
