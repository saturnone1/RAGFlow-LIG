import { BrandSignature } from '@/brand/brand-logo';
import { BrandVideo } from '@/brand/brand-video';
import { LIG_BRAND, localizedBrandCopy } from '@/brand/config';
import { useTranslation } from 'react-i18next';

export function Banner() {
  return <NextBanner />;
}
export function NextBanner() {
  const { i18n } = useTranslation();
  const copy = localizedBrandCopy(i18n.language, LIG_BRAND.homeCopy);

  return (
    <section className="lig-home-hero" aria-label={LIG_BRAND.productName}>
      <BrandVideo className="lig-home-hero-media" />
      <div className="lig-home-hero-shade" />
      <div className="lig-home-hero-content">
        <BrandSignature inverse className="lig-home-signature" />
        <p className="lig-home-kicker">AI KNOWLEDGE HUB</p>
        <h1>{copy}</h1>
        <p>{LIG_BRAND.productName}</p>
      </div>
      <div className="lig-home-diagonal" aria-hidden />
    </section>
  );
}
