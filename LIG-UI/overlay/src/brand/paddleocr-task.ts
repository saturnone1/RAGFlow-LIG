export const PADDLEOCR_WHOLE_PDF_TASK_PAGE_SIZE = 100_000_000;

export function configurePaddleOcrWholePdf<T extends Record<string, unknown>>(
  parserConfig: T | undefined,
): T | undefined {
  if (!parserConfig) return parserConfig;

  const layoutRecognizer = parserConfig.layout_recognize;
  if (
    typeof layoutRecognizer !== 'string' ||
    !layoutRecognizer.toLowerCase().includes('paddleocr-from-env')
  ) {
    return parserConfig;
  }

  return {
    ...parserConfig,
    task_page_size: PADDLEOCR_WHOLE_PDF_TASK_PAGE_SIZE,
  };
}
