// ──────────────────────────────────────────────────────────────────────────
// Natural ("human") sort for composite lot codes.
//
// Plain string sort gets these wrong: "VIT...0002..." would land after
// "VIT...0010..." because '1' < '2' character by character. Field staff expect
// 2 before 10. So we split each id into alternating letter/number chunks and
// compare chunk by chunk — numbers numerically, letters lexically.
//
//   compareLotIds("VIT1MALC000224", "VIT1MALC001024")  ->  -1  (2 before 10)
// ──────────────────────────────────────────────────────────────────────────

const CHUNK = /(\d+|\D+)/g;

export function compareLotIds(a = "", b = "") {
  const aParts = a.match(CHUNK) || [];
  const bParts = b.match(CHUNK) || [];
  const len = Math.min(aParts.length, bParts.length);

  for (let i = 0; i < len; i++) {
    const ap = aParts[i];
    const bp = bParts[i];
    const aNum = /^\d+$/.test(ap);
    const bNum = /^\d+$/.test(bp);

    if (aNum && bNum) {
      const diff = parseInt(ap, 10) - parseInt(bp, 10);
      if (diff !== 0) return Math.sign(diff);
    } else if (!aNum && !bNum) {
      const diff = ap.localeCompare(bp);
      if (diff !== 0) return Math.sign(diff);
    } else {
      // Numbers sort before letters at the same position.
      return aNum ? 1 : -1;
    }
  }
  return Math.sign(aParts.length - bParts.length);
}
