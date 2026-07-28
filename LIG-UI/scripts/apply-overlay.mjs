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

content = read('src/pages/dataset/dataset-setting/saving-button.tsx');
content =
  "import { configurePaddleOcrWholePdf } from '@/brand/paddleocr-task';\n" +
  content;
content = replaceOnce(
  content,
  `                  parser_config: {
                    ...values.parser_config,`,
  `                  parser_config: {
                    ...configurePaddleOcrWholePdf(values.parser_config),`,
  'PaddleOCR whole-PDF task configuration',
);
write('src/pages/dataset/dataset-setting/saving-button.tsx', content);

content = read('src/components/file-upload-dialog/index.tsx');
content =
  "import { getUploadFile, getUploadFilePasswordKey, isPdfUpload } from '@/brand/pdf-password';\n" +
  content;
content = replaceOnce(
  content,
  "import { Switch } from '../ui/switch';",
  "import { Switch } from '../ui/switch';\nimport { Input } from '../ui/input';",
  'PDF password upload input import',
);
content = replaceOnce(
  content,
  "    tableColumnMode: z.enum(['auto', 'manual']).optional(),",
  "    pdfPasswords: z.record(z.string().max(1024)).optional(),\n    tableColumnMode: z.enum(['auto', 'manual']).optional(),",
  'PDF password upload schema',
);
content = replaceOnce(
  content,
  "      fileList: [],\n      tableColumnMode: 'auto',",
  "      fileList: [],\n      pdfPasswords: {},\n      tableColumnMode: 'auto',",
  'PDF password upload defaults',
);
content = replaceOnce(
  content,
  "  const [extractedColumns, setExtractedColumns] = useState<string[]>([]);",
  "  const selectedFiles = form.watch('fileList');\n  const pdfFiles = selectedFiles.filter(isPdfUpload);\n\n  const [extractedColumns, setExtractedColumns] = useState<string[]>([]);",
  'selected PDF upload files',
);
content = replaceOnce(
  content,
  `        </RAGFlowFormItem>

        {showColumnConfig && (`,
  `        </RAGFlowFormItem>

        {pdfFiles.length > 0 && (
          <div className="space-y-3 rounded-md border p-3">
            <div>
              <Label className="text-sm font-medium">
                {t('fileManager.pdfPasswords')}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t('fileManager.pdfPasswordsTip')}
              </p>
            </div>
            {pdfFiles.map((value) => {
              const file = getUploadFile(value);
              const passwordKey = getUploadFilePasswordKey(value);
              return (
                <RAGFlowFormItem
                  key={passwordKey}
                  name={\`pdfPasswords.\${passwordKey}\`}
                  label={file.name}
                >
                  {(field) => (
                    <Input
                      {...field}
                      value={field.value || ''}
                      type="password"
                      autoComplete="new-password"
                      placeholder={t('fileManager.pdfPasswordPlaceholder')}
                    />
                  )}
                </RAGFlowFormItem>
              );
            })}
          </div>
        )}

        {showColumnConfig && (`,
  'per-file PDF password inputs',
);
write('src/components/file-upload-dialog/index.tsx', content);

content = read('src/pages/dataset/dataset/use-upload-document.ts');
content = replaceOnce(
  content,
  "      tableColumnRoles,\n    }: UploadFormSchemaType) => {",
  "      tableColumnRoles,\n      pdfPasswords,\n    }: UploadFormSchemaType) => {",
  'PDF passwords upload form value',
);
content = replaceOnce(
  content,
  '        const ret = await uploadDocument(fileList as File[], parserConfig);',
  '        const ret = await uploadDocument(fileList, parserConfig, pdfPasswords);',
  'submit PDF passwords',
);
write('src/pages/dataset/dataset/use-upload-document.ts', content);

content = read('src/hooks/use-document-request.ts');
content =
  "import { getUploadFile, getUploadFilePasswordKey, type UploadFileValue } from '@/brand/pdf-password';\n" +
  content;
content = replaceOnce(
  content,
  '{ fileList: File[]; parserConfig?: Record<string, any> }',
  '{ fileList: UploadFileValue[]; parserConfig?: Record<string, any>; pdfPasswords?: Record<string, string> }',
  'upload mutation PDF password type',
);
content = replaceOnce(
  content,
  'mutationFn: async ({ fileList, parserConfig }) => {',
  'mutationFn: async ({ fileList, parserConfig, pdfPasswords }) => {',
  'upload mutation PDF passwords',
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
  "      if (parserConfig) {\n        formData.append('parser_config', JSON.stringify(parserConfig));\n      }\n      if (pdfPasswords) {\n        const passwords = fileList.map(\n          (file) => pdfPasswords[getUploadFilePasswordKey(file)] || null,\n        );\n        formData.append('pdf_passwords', JSON.stringify(passwords));\n      }",
  'upload PDF password form data',
);
content = replaceOnce(
  content,
  "    (fileList: File[], parserConfig?: Record<string, any>) =>\n      mutateAsync({ fileList, parserConfig }),",
  "    (\n      fileList: UploadFileValue[],\n      parserConfig?: Record<string, any>,\n      pdfPasswords?: Record<string, string>,\n    ) => mutateAsync({ fileList, parserConfig, pdfPasswords }),",
  'upload callback PDF password argument',
);
write('src/hooks/use-document-request.ts', content);

content = read('src/interfaces/database/document.ts');
content = replaceOnce(
  content,
  '  enable_metadata?: boolean;\n}',
  '  enable_metadata?: boolean;\n  pdf_password_configured?: boolean;\n  pdf_password?: string;\n  clear_pdf_password?: boolean;\n}',
  'document PDF password status',
);
write('src/interfaces/database/document.ts', content);

content = read('src/interfaces/request/document.ts');
content = replaceOnce(
  content,
  '  enable_metadata?: boolean;\n}',
  '  enable_metadata?: boolean;\n  pdf_password?: string | null;\n  clear_pdf_password?: boolean;\n}',
  'document PDF password update request',
);
write('src/interfaces/request/document.ts', content);

content = read('src/components/chunk-method-dialog/index.tsx');
content = replaceOnce(
  content,
  "        task_page_size: z.coerce.number().optional(),",
  "        task_page_size: z.coerce.number().optional(),\n        pdf_password: z.string().max(1024).optional(),\n        clear_pdf_password: z.boolean().optional(),",
  'document PDF password form schema',
);
content = replaceOnce(
  content,
  '    const parserConfig = data.parser_config;',
  `    const {
      pdf_password: pdfPassword,
      clear_pdf_password: clearPdfPassword,
      ...parserConfig
    } = data.parser_config;`,
  'extract document PDF password update',
);
content = replaceOnce(
  content,
  "        pages: parserConfig?.pages?.map((x: any) => [x.from, x.to]) ?? [],",
  "        pages: parserConfig?.pages?.map((x: any) => [x.from, x.to]) ?? [],\n        ...(clearPdfPassword\n          ? { pdf_password: null, clear_pdf_password: true }\n          : pdfPassword\n            ? { pdf_password: pdfPassword }\n            : {}),",
  'submit changed document PDF password',
);
content = replaceOnce(
  content,
  "          ...omit(parserConfig, 'pages'),",
  "          ...omit(parserConfig, ['pages', 'pdf_password_configured']),\n          pdf_password: '',\n          clear_pdf_password: false,",
  'reset private document PDF password fields',
);
content = replaceOnce(
  content,
  `              {showPages && parseType === ParseType.BuiltIn && (
                <DynamicPageRange />
              )}`,
  `              {isPdf && (
                <div className="space-y-3 rounded-md border p-3">
                  <FormField
                    control={form.control}
                    name="parser_config.pdf_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('fileManager.pdfPassword')}</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            value={field.value || ''}
                            type="password"
                            autoComplete="new-password"
                            disabled={form.watch(
                              'parser_config.clear_pdf_password',
                            )}
                            placeholder={
                              parserConfig?.pdf_password_configured
                                ? t('fileManager.pdfPasswordKeepPlaceholder')
                                : t('fileManager.pdfPasswordPlaceholder')
                            }
                          />
                        </FormControl>
                        <p className="text-sm text-muted-foreground">
                          {t('fileManager.pdfPasswordUpdateTip')}
                        </p>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  {parserConfig?.pdf_password_configured && (
                    <FormField
                      control={form.control}
                      name="parser_config.clear_pdf_password"
                      render={({ field }) => (
                        <FormItem className="flex items-center justify-between gap-4">
                          <FormLabel>{t('fileManager.pdfPasswordClear')}</FormLabel>
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
  'document PDF password settings',
);
content = replaceOnce(
  content,
  "import { Input } from '../ui/input';",
  "import { Input } from '../ui/input';\nimport { Switch } from '../ui/switch';",
  'document PDF password clear switch',
);
write('src/components/chunk-method-dialog/index.tsx', content);

for (const [localePath, values] of [
  ['src/locales/en.ts', {
    label: 'PDF passwords',
    tip: 'Enter a password for each protected PDF. Unprotected PDFs can be left blank.',
    password: 'PDF password',
    placeholder: 'Enter the PDF password',
    keep: 'Leave blank to keep the saved password',
    update: 'Save a new password here, then run the document again. The password is never returned by the API.',
    clear: 'Remove the saved PDF password',
  }],
  ['src/locales/ko.ts', {
    label: 'PDF 비밀번호',
    tip: '암호가 설정된 PDF마다 비밀번호를 입력하세요. 암호가 없는 PDF는 비워 두면 됩니다.',
    password: 'PDF 비밀번호',
    placeholder: 'PDF 비밀번호 입력',
    keep: '비워 두면 저장된 비밀번호를 유지합니다',
    update: '새 비밀번호를 저장한 뒤 문서를 다시 실행하세요. 비밀번호는 API 응답에 노출되지 않습니다.',
    clear: '저장된 PDF 비밀번호 제거',
  }],
]) {
  content = read(localePath);
  content = replaceOnce(
    content,
    "      parseOnCreation: " + (localePath.endsWith('/ko.ts') ? "'생성 시 파싱'," : "'Parse on creation',"),
    "      parseOnCreation: " + (localePath.endsWith('/ko.ts') ? "'생성 시 파싱'," : "'Parse on creation',") +
      `\n      pdfPasswords: '${values.label}',\n      pdfPasswordsTip: '${values.tip}',\n      pdfPassword: '${values.password}',\n      pdfPasswordPlaceholder: '${values.placeholder}',\n      pdfPasswordKeepPlaceholder: '${values.keep}',\n      pdfPasswordUpdateTip: '${values.update}',\n      pdfPasswordClear: '${values.clear}',`,
    `PDF password ${localePath} locale`,
  );
  write(localePath, content);
}

cpSync(overlayRoot, webRoot, { recursive: true, force: true });

console.log('LIG AI Knowledge Hub overlay applied successfully.');
