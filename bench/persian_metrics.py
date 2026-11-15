"""Persian text normalisation + CER / WER metrics for OCR benchmarking.

Used by the IDPL-PFOD benchmark runner.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Arabic diacritics + Quranic marks + tatweel
_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_ZWNJ = "\u200c"
_ZWJ = "\u200d"

# Arabic -> Persian letter unification (compatible for CER purposes)
_CHAR_MAP = {
    "\u064a": "\u06cc",  # ي -> ی
    "\u0649": "\u06cc",  # ى -> ی
    "\u0643": "\u06a9",  # ك -> ک
    "\u0629": "\u0647",  # ة -> ه
    "\u06c0": "\u0647",  # ۀ -> ه
    "\u0623": "\u0627",  # أ -> ا
    "\u0625": "\u0627",  # إ -> ا
    "\u0622": "\u0627",  # آ -> ا
    "\u0624": "\u0648",  # ؤ -> و
}

_TRANSLATE = {ord(k): v for k, v in _CHAR_MAP.items()}

_DIGITS = {ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}
_DIGITS.update({ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")})

_PUNCT = "«»‹›“”\"'`؛،:,.;!?؟…—–-_()[]{}<>/\\|*#@$%&+=~^"


def normalize(text: str, drop_spaces: bool = False) -> str:
    """Normalise Persian/Arabic OCR text for fair CER comparison."""
    if text is None:
        return ""
    t = unicodedata.normalize("NFKC", str(text))
    t = t.replace(_ZWNJ, "").replace(_ZWJ, "")
    t = _DIACRITICS.sub("", t)
    t = t.translate(_TRANSLATE)
    t = t.translate(_DIGITS)
    t = t.lower()
    if drop_spaces:
        t = re.sub(r"\s+", "", t)
        t = t.translate({ord(c): None for c in _PUNCT})
    else:
        t = re.sub(r"\s+", " ", t).strip()
    return t


def levenshtein(a: str, b: str) -> int:
    """Unit-cost edit distance (two-row DP)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(ref: str, hyp: str) -> float:
    """Character error rate (not clipped at 1.0)."""
    ref_n = normalize(ref, drop_spaces=True)
    hyp_n = normalize(hyp, drop_spaces=True)
    if not ref_n:
        return 0.0 if not hyp_n else 1.0
    return levenshtein(ref_n, hyp_n) / len(ref_n)


def wer(ref: str, hyp: str) -> float:
    """Word error rate on whitespace tokens."""
    r = normalize(ref).split()
    h = normalize(hyp).split()
    if not r:
        return 0.0 if not h else 1.0
    return levenshtein(r, h) / len(r)


def summarize(pairs: Iterable[tuple[str, str]]) -> dict:
    """Aggregate CER/WER over (reference, hypothesis) pairs.

    Reports both the mean of per-line rates and the corpus rate
    (sum of edit distances / sum of reference lengths), which is the
    metric used in the IDPL-PFOD paper family.
    """
    pairs = list(pairs)
    total_chars = 0
    total_char_err = 0
    total_words = 0
    total_word_err = 0
    per_line_cer: list[float] = []
    exact = 0

    for ref, hyp in pairs:
        r = normalize(ref, drop_spaces=True)
        h = normalize(hyp, drop_spaces=True)
        if r:
            total_chars += len(r)
            total_char_err += levenshtein(r, h)
            per_line_cer.append(levenshtein(r, h) / len(r))
        rw = normalize(ref).split()
        hw = normalize(hyp).split()
        if rw:
            total_words += len(rw)
            total_word_err += levenshtein(rw, hw)
        if r == h:
            exact += 1

    n = len(pairs) or 1
    corpus_cer = total_char_err / total_chars if total_chars else 1.0
    corpus_wer = total_word_err / total_words if total_words else 1.0
    return {
        "n": len(pairs),
        "corpus_cer": corpus_cer,
        "corpus_wer": corpus_wer,
        "corpus_char_accuracy": max(0.0, 1.0 - corpus_cer) * 100.0,
        "mean_line_cer": (sum(per_line_cer) / len(per_line_cer)) if per_line_cer else 1.0,
        "mean_line_accuracy": max(0.0, 1.0 - (sum(per_line_cer) / len(per_line_cer))) * 100.0 if per_line_cer else 0.0,
        "exact_match": exact / n * 100.0,
        "total_chars": total_chars,
        "total_words": total_words,
    }


if __name__ == "__main__":
    ref = "بسم الله الرحمن الرحیم"
    hyp = "بسم الله الرحمان الرحیم"
    print("cer:", round(cer(ref, hyp), 4), "wer:", round(wer(ref, hyp), 4))
    print(summarize([(ref, hyp)]))
