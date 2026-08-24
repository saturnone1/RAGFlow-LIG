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

const apiModeOptions = [
  { label: 'Auto', value: 'auto' },
  { label: 'RAGFlow Job API', value: 'job' },
  { label: 'PaddleX Image API', value: 'direct-image' },
];

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
  const isManagedPaddleOCR =
    normalizedSelection.includes('paddleocr-from-env') ||
    normalizedSelection.includes('paddleocr-vl-from-env');

  if (!isPaddleOCRSelected) {
    return null;
  }

  if (isManagedPaddleOCR) {
    const isKorean = i18n.resolvedLanguage?.toLowerCase().startsWith('ko');

    return (
      <div className="ml-2 border-l-2 border-primary/30 pl-4">
        <div className="text-sm font-medium text-text-secondary">
          {isKorean
            ? '내부 OCR 모델이 자동 구성되었습니다.'
            : 'The internal OCR model is configured automatically.'}
        </div>
        <div className="mt-1 text-xs leading-5 text-text-sub-title-invert">
          {isKorean
            ? '일반 PaddleOCR와 PaddleOCR-VL은 서로 다른 내부 URL·토큰·알고리즘으로 저장됩니다. 이 화면에서 별도 값을 입력할 필요가 없습니다.'
            : 'PaddleOCR and PaddleOCR-VL keep separate internal URLs, tokens, and algorithms; no additional value is required here.'}
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

      <RAGFlowFormItem
        name={buildName('paddleocr_api_mode')}
        label={
          i18n.resolvedLanguage?.startsWith('ko') ? 'API 방식' : 'API Mode'
        }
        tooltip={
          i18n.resolvedLanguage?.startsWith('ko')
            ? '자동은 번들 내부 주소에 Job API, 외부 주소에 PaddleX 이미지 API를 사용합니다.'
            : 'Auto uses the Job API for bundled endpoints and the PaddleX image API for external endpoints.'
        }
        horizontal={true}
      >
        {(field) => (
          <RAGFlowSelect
            value={field.value || 'auto'}
            onChange={field.onChange}
            options={apiModeOptions}
          />
        )}
      </RAGFlowFormItem>

      <RAGFlowFormItem
        name={buildName('paddleocr_direct_workers')}
        label={
          i18n.resolvedLanguage?.startsWith('ko')
            ? '이미지 API 동시 요청'
            : 'Concurrent Image Requests'
        }
        tooltip={
          i18n.resolvedLanguage?.startsWith('ko')
            ? 'PaddleX 이미지 API에 동시에 보낼 페이지 수입니다. Job API에는 적용되지 않습니다.'
            : 'Pages sent concurrently to the PaddleX image API. This does not affect the Job API.'
        }
        horizontal={true}
      >
        {(field) => (
          <Input {...field} type="number" min={1} value={field.value || 8} />
        )}
      </RAGFlowFormItem>

      <RAGFlowFormItem
        name={buildName('paddleocr_direct_render_dpi')}
        label={
          i18n.resolvedLanguage?.startsWith('ko')
            ? 'PDF 이미지 해상도(DPI)'
            : 'PDF Image Resolution (DPI)'
        }
        tooltip={
          i18n.resolvedLanguage?.startsWith('ko')
            ? 'PaddleX 이미지 API로 보내기 전에 PDF 페이지를 렌더링하는 해상도입니다. 기본 144 DPI이며 작은 글자가 많은 스캔 문서는 216 DPI를 시험하십시오.'
            : 'Resolution used to render PDF pages before sending them to the PaddleX image API. The default is 144 DPI; try 216 DPI for scans with very small text.'
        }
        horizontal={true}
      >
        {(field) => (
          <Input {...field} type="number" min={1} value={field.value || 144} />
        )}
      </RAGFlowFormItem>
    </div>
  );
}
