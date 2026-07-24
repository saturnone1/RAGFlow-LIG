export const LIG_BRAND = {
  productName: 'LIG AI Knowledge Hub',
  primary: '#002F6D',
  secondary: '#D0D3D4',
  signatureBlue: '/brand/lig-signature-blue.png',
  signatureWhite: '/brand/lig-signature-white.png',
  heroVideo: '/brand/company-hero.mp4',
  heroPoster: '/brand/company-hero-poster.jpg',
  tagline: {
    ko: '신뢰할 수 있는 사내 지식을 하나로 연결합니다',
    en: 'Connect trusted knowledge. Accelerate decisions.',
  },
  homeCopy: {
    ko: '지식을 연결하고, 더 빠른 판단을 지원합니다',
    en: 'Connected knowledge for faster decisions',
  },
} as const;

export function localizedBrandCopy(
  language: string | undefined,
  copy: { ko: string; en: string },
) {
  return language?.toLowerCase().startsWith('ko') ? copy.ko : copy.en;
}
