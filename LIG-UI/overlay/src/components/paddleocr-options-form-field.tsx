import { RAGFlowFormItem } from '@/components/ragflow-form';
import { Input } from '@/components/ui/input';
import { RAGFlowSelect } from '@/components/ui/select';
import { LLMFactory } from '@/constants/llm';
import { buildOptions } from '@/utils/form';
import { useFormContext, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

const algorithmOptions = buildOptions([
  'PaddleOCR-VL-1.6',
  'PaddleOCR-VL-1.5',
  'PaddleOCR-VL',
  'PP-OCRv6',
  'PP-OCRv5',
  'PP-StructureV3',
]);

export function PaddleOCROptionsFormField({
  namePrefix = 'parser_config',
}: {
  namePrefix?: string;
}) {
  const form = useFormContext();
  const { i18n, t } = useTranslation();
  const buildName = (field: string) =>
    namePrefix ? `${namePrefix}.${field}` : field;

  const layoutRecognize = useWatch({
    control: form.control,
    name: 'parser_config.layout_recognize',
  });
  const normalizedSelection = String(layoutRecognize ?? '').toLowerCase();
  const isPaddleOCRSelected =
    normalizedSelection.includes(LLMFactory.PaddleOCR.toLowerCase()) ||
    normalizedSelection.includes('paddleocr');
  const isManagedPaddleOCR = normalizedSelection.includes(
    'paddleocr-from-env',
  );

  if (!isPaddleOCRSelected) {
    return null;
  }

  if (isManagedPaddleOCR) {
    const isKorean = i18n.resolvedLanguage?.toLowerCase().startsWith('ko');

    return (
      <div className="ml-2 border-l-2 border-primary/30 pl-4">
        <div className="text-sm font-medium text-text-secondary">
          {isKorean
            ? '내부 한국어 OCR이 자동 구성되었습니다.'
            : 'Internal Korean OCR is configured automatically.'}
        </div>
        <div className="mt-1 text-xs leading-5 text-text-sub-title-invert">
          {isKorean
            ? 'PP-OCRv5와 내부 전용 연결을 사용하므로 API URL이나 토큰을 입력할 필요가 없습니다.'
            : 'PP-OCRv5 and the private internal connection are already set; no API URL or token is required.'}
        </div>
      </div>
    );
  }

  return (
    <div className="ml-2 space-y-4 border-l-2 border-primary/30 pl-4">
      <div className="text-sm font-medium text-text-secondary">
        {t('knowledgeConfiguration.paddleocrOptions', 'PaddleOCR Options')}
      </div>

      <RAGFlowFormItem
        name={buildName('paddleocr_api_url')}
        label={t('knowledgeConfiguration.paddleocrApiUrl', 'PaddleOCR API URL')}
        tooltip={t(
          'knowledgeConfiguration.paddleocrApiUrlTip',
          'The API endpoint URL for PaddleOCR service',
        )}
        horizontal={true}
      >
        {(field) => (
          <Input
            {...field}
            placeholder={t('knowledgeConfiguration.paddleocrApiUrlPlaceholder')}
          />
        )}
      </RAGFlowFormItem>

      <RAGFlowFormItem
        name={buildName('paddleocr_access_token')}
        label={t(
          'knowledgeConfiguration.paddleocrAccessToken',
          'AI Studio Access Token',
        )}
        tooltip={t(
          'knowledgeConfiguration.paddleocrAccessTokenTip',
          'Access token for PaddleOCR API (optional)',
        )}
        horizontal={true}
      >
        {(field) => (
          <Input
            {...field}
            placeholder={t(
              'knowledgeConfiguration.paddleocrAccessTokenPlaceholder',
            )}
          />
        )}
      </RAGFlowFormItem>

      <RAGFlowFormItem
        name={buildName('paddleocr_algorithm')}
        label={t(
          'knowledgeConfiguration.paddleocrAlgorithm',
          'PaddleOCR Algorithm',
        )}
        tooltip={t(
          'knowledgeConfiguration.paddleocrAlgorithmTip',
          'Algorithm to use for PaddleOCR parsing',
        )}
        horizontal={true}
      >
        {(field) => (
          <RAGFlowSelect
            value={field.value || undefined}
            onChange={field.onChange}
            options={algorithmOptions}
            placeholder={t('common.selectPlaceholder', 'Select value')}
          />
        )}
      </RAGFlowFormItem>
    </div>
  );
}
