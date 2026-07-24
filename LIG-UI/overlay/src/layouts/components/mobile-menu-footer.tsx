import { LIG_BRAND } from '@/brand/config';

type MobileMenuFooterProps = {
  onClose: () => void;
};

export function MobileMenuFooter({ onClose }: MobileMenuFooterProps) {
  return (
    <div className="shrink-0 border-t border-border-button px-4 py-4">
      <button
        type="button"
        onClick={onClose}
        className="w-full text-center text-xs font-semibold text-text-secondary transition-colors hover:text-text-primary"
      >
        {LIG_BRAND.productName}
      </button>
    </div>
  );
}
