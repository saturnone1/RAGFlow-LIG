import { PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { BrandSignature } from './brand-logo';
import { BrandVideo } from './brand-video';
import { LIG_BRAND, localizedBrandCopy } from './config';

export function BrandLoginShell({ children }: PropsWithChildren) {
  const { i18n } = useTranslation();
  const tagline = localizedBrandCopy(i18n.language, LIG_BRAND.tagline);

  return (
    <main className="lig-login-shell">
      <section className="lig-login-visual" aria-label={LIG_BRAND.productName}>
        <BrandVideo className="lig-login-media" />
        <div className="lig-login-shade" />
        <div className="lig-login-visual-content">
          <BrandSignature inverse className="lig-login-signature" />
          <div className="lig-diagonal-mark" aria-hidden />
          <p className="lig-login-kicker">SECURE KNOWLEDGE PLATFORM</p>
          <h1>{LIG_BRAND.productName}</h1>
          <p className="lig-login-tagline">{tagline}</p>
        </div>
      </section>

      <section className="lig-login-form-panel">
        <div className="lig-login-mobile-brand">
          <BrandSignature className="lig-login-mobile-signature" />
          <strong>{LIG_BRAND.productName}</strong>
        </div>
        <div className="lig-login-form-wrap">{children}</div>
        <p className="lig-login-copyright">
          © LIG Defense &amp; Aerospace. All rights reserved.
        </p>
      </section>
    </main>
  );
}
