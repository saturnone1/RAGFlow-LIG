export type UploadFileValue =
  | File
  | {
      file: File;
      path?: string;
    };

export function getUploadFile(value: UploadFileValue): File {
  return value instanceof File ? value : value.file;
}

export function isPdfUpload(value: UploadFileValue): boolean {
  return getUploadFile(value).name.toLowerCase().endsWith('.pdf');
}

export function getUploadFilePasswordKey(value: UploadFileValue): string {
  const file = getUploadFile(value);
  const path = value instanceof File ? file.webkitRelativePath : value.path;
  const identity = `${path || file.name}\0${file.size}\0${file.lastModified}`;
  return Array.from(identity, (character) =>
    character.codePointAt(0)!.toString(16),
  ).join('-');
}
