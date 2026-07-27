import { ParseType } from '@/constants/knowledge';
import {
  configurePaddleOcrWholePdf,
  PADDLEOCR_WHOLE_PDF_TASK_PAGE_SIZE,
} from '@/brand/paddleocr-task';
import { formSchema } from './form-schema';

describe('dataset settings schema', () => {
  it('accepts nullable table configuration returned by the dataset API', () => {
    const result = formSchema.safeParse({
      parse_type: ParseType.BuiltIn,
      name: 'MIL-STD-2525C',
      language: 'English',
      chunk_method: 'naive',
      embedding_model: 'embedding-model',
      pagerank: 0,
      parser_config: {
        layout_recognize:
          'paddleocr-from-env@paddleocr-from-env@PaddleOCR',
        chunk_token_num: 512,
        delimiter: '\n',
        enable_children: false,
        children_delimiter: '',
        html4excel: false,
        table_column_mode: null,
        table_column_roles: null,
        table_column_names: null,
        raptor: { use_raptor: false },
        graphrag: { use_graphrag: false },
      },
    });

    expect(result.success).toBe(true);
  });

  it('configures a PaddleOCR PDF as one ingestion task', () => {
    const parserConfig = configurePaddleOcrWholePdf({
      layout_recognize: 'paddleocr-from-env@paddleocr-from-env@PaddleOCR',
      task_page_size: 12,
    });

    expect(parserConfig?.task_page_size).toBe(
      PADDLEOCR_WHOLE_PDF_TASK_PAGE_SIZE,
    );
  });

  it('does not change the task size for other parsers', () => {
    const parserConfig = { layout_recognize: 'DeepDOC', task_page_size: 12 };

    expect(configurePaddleOcrWholePdf(parserConfig)).toBe(parserConfig);
  });
});
