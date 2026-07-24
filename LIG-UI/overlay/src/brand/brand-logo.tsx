import { LIG_BRAND } from './config';

export function BrandSignature({
  inverse = false,
  className = '',
}: {
  inverse?: boolean;
  className?: string;
}) {
  return (
    <img
      src={inverse ? LIG_BRAND.signatureWhite : LIG_BRAND.signatureBlue}
      alt="LIG Defense & Aerospace"
      className={className}
    />
  );
}
export function BrandHeaderLogo() {
  return (
    <span className="lig-header-brand" aria-label={LIG_BRAND.productName}>
      <BrandSignature className="lig-header-signature lig-logo-light" />
      <BrandSignature
        inverse
        className="lig-header-signature lig-logo-dark"
      />
      <span className="lig-header-divider" aria-hidden />
      <span className="lig-header-product">{LIG_BRAND.productName}</span>
    </span>
  );
}
