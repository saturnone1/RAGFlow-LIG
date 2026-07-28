import {
  getUploadFile,
  getUploadFilePasswordKey,
  isPdfUpload,
} from './pdf-password';

describe('PDF upload password identity', () => {
  it('keeps different same-name files separate and recognizes PDF case-insensitively', () => {
    const first = new File(['first'], '보안.PDF', { lastModified: 1 });
    const second = new File(['second'], '보안.PDF', { lastModified: 2 });

    expect(isPdfUpload(first)).toBe(true);
    expect(getUploadFilePasswordKey(first)).not.toBe(
      getUploadFilePasswordKey(second),
    );
  });

  it('uses folder paths and unwraps folder upload values', () => {
    const file = new File(['pdf'], 'document.pdf', { lastModified: 1 });
    const first = { file, path: 'folder-a/document.pdf' };
    const second = { file, path: 'folder-b/document.pdf' };

    expect(getUploadFile(first)).toBe(file);
    expect(getUploadFilePasswordKey(first)).not.toBe(
      getUploadFilePasswordKey(second),
    );
  });
});
