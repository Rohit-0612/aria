import { motion } from 'framer-motion';
import type { ConsultationError } from '../lib/types';
import { Icon } from './Icon';

/*
  A failed consultation.

  Deliberately built from none of the answer furniture: no prose typography,
  no citation markers, no certainty chip, no confidence gauge. It reads as an
  instrument fault, not as guidance — which is the whole point. A clinician
  glancing at this must never mistake it for something ARIA concluded.
*/

const ease = [0.22, 1, 0.36, 1] as const;

export function ErrorNotice({ error }: { error: ConsultationError }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease }}
      role="alert"
      className="flex gap-2.5 rounded-r-[8px] border-l-2 border-oxblood bg-oxblood/[0.06] py-2.5 pl-3 pr-3.5"
    >
      <span className="mt-[3px] shrink-0 text-oxblood">
        <Icon name="caution" size={15} />
      </span>
      <span className="min-w-0">
        <span className="font-mono text-[0.58rem] uppercase tracking-[0.14em] text-oxblood">
          No answer produced
        </span>
        <span className="mt-1 block font-prose text-[0.88rem] leading-relaxed text-ink-soft">
          {error.message}
        </span>
        <span className="mt-1.5 block font-mono text-[0.56rem] uppercase tracking-[0.1em] text-ink-faint">
          {error.stage} · {error.code}
        </span>
      </span>
    </motion.div>
  );
}
