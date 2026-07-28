import {
  documentPasswordsSchema,
  getUploadFile,
  getUploadFilePasswordKey,
  supportsDocumentPassword,
} from './document-password';

describe('document upload password identity', () => {
  it('keeps password fields optional when they were not touched', () => {
    expect(documentPasswordsSchema.parse(undefined)).toBeUndefined();
    expect(
      documentPasswordsSchema.parse({ untouched: undefined, blank: '' }),
    ).toEqual({ untouched: '', blank: '' });
  });

  it.each(['pdf', 'DOCX', 'xlsx', 'Pptx', 'hwp', 'HWPX'])(
    'recognizes the %s extension',
    (extension) => {
      expect(
        supportsDocumentPassword(
          new File(['document'], `보안문서.${extension}`, { lastModified: 1 }),
        ),
      ).toBe(true);
    },
  );

  it('does not offer passwords for unrelated files', () => {
    expect(supportsDocumentPassword(new File(['text'], 'notes.txt'))).toBe(false);
  });

  it('keeps different same-name files separate', () => {
    const first = new File(['first'], '보안.PDF', { lastModified: 1 });
    const second = new File(['second'], '보안.PDF', { lastModified: 2 });
    expect(getUploadFilePasswordKey(first)).not.toBe(
      getUploadFilePasswordKey(second),
    );
  });

  it('uses folder paths and unwraps folder upload values', () => {
    const file = new File(['document'], 'document.docx', { lastModified: 1 });
    const first = { file, path: 'folder-a/document.docx' };
    const second = { file, path: 'folder-b/document.docx' };

    expect(getUploadFile(first)).toBe(file);
    expect(getUploadFilePasswordKey(first)).not.toBe(
      getUploadFilePasswordKey(second),
    );
  });
});
