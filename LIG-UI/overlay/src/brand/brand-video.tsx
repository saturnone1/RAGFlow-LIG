import { useEffect, useState } from 'react';
import { LIG_BRAND } from './config';

type NetworkInformation = {
  saveData?: boolean;
  effectiveType?: string;
};

export function BrandVideo({ className = '' }: { className?: string }) {
  const [canPlayVideo, setCanPlayVideo] = useState(false);

  useEffect(() => {
    const reduceMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches;
    const connection = (
      navigator as Navigator & { connection?: NetworkInformation }
    ).connection;
    const slowConnection =
      connection?.saveData || ['slow-2g', '2g'].includes(connection?.effectiveType || '');
    setCanPlayVideo(
      window.matchMedia('(min-width: 768px)').matches &&
        !reduceMotion &&
        !slowConnection,
    );
  }, []);

  if (!canPlayVideo) {
    return (
      <img
        src={LIG_BRAND.heroPoster}
        alt=""
        aria-hidden
        className={className}
      />
    );
  }

  return (
    <video
      className={className}
      autoPlay
      muted
      loop
      playsInline
      preload="metadata"
      poster={LIG_BRAND.heroPoster}
      aria-hidden
    >
      <source src={LIG_BRAND.heroVideo} type="video/mp4" />
    </video>
  );
}
