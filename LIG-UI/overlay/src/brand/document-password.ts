import { z } from 'zod';

export type UploadFileValue =
  | File
  | {
      file: File;
      path?: string;
    };

const passwordExtensions = new Set([
  'pdf',
  'doc',
  'docx',
  'xls',
  'xlsx',
  'ppt',
  'pptx',
  'hwp',
  'hwpx',
]);

export const documentPasswordsSchema = z
  .record(z.string().max(1024).default(''))
  .optional();

export function getUploadFile(value: UploadFileValue): File {
  return value instanceof File ? value : value.file;
}

export function supportsDocumentPassword(value: UploadFileValue): boolean {
  const extension = getUploadFile(value).name.toLowerCase().split('.').pop();
  return supportsPasswordExtension(extension);
}

export function supportsPasswordExtension(extension?: string): boolean {
  return extension !== undefined && passwordExtensions.has(extension.toLowerCase());
}

export function getUploadFilePasswordKey(value: UploadFileValue): string {
  const file = getUploadFile(value);
  const path = value instanceof File ? file.webkitRelativePath : value.path;
  const identity = `${path || file.name}\0${file.size}\0${file.lastModified}`;
  return Array.from(identity, (character) =>
    character.codePointAt(0)!.toString(16),
  ).join('-');
}
