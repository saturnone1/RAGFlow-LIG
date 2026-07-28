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

const maxDocumentPasswordBytes = 1024;

function utf8ByteLength(value: string): number {
  let bytes = 0;
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit < 0x80) bytes += 1;
    else if (codeUnit < 0x800) bytes += 2;
    else if (
      codeUnit >= 0xd800 &&
      codeUnit <= 0xdbff &&
      index + 1 < value.length &&
      value.charCodeAt(index + 1) >= 0xdc00 &&
      value.charCodeAt(index + 1) <= 0xdfff
    ) {
      bytes += 4;
      index += 1;
    } else bytes += 3;
  }
  return bytes;
}

export const documentPasswordSchema = z.string().refine(
  (password) => utf8ByteLength(password) <= maxDocumentPasswordBytes,
  `Password must be at most ${maxDocumentPasswordBytes} UTF-8 bytes`,
);

export const documentPasswordsSchema = z
  .record(documentPasswordSchema.default(''))
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
