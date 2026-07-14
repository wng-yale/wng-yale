"""
Shared core for journalistic style + narrative metrics.

Used by per-source builders (FT, IMM, Statist) to produce comparable
monthly time-series of stylistic and narrative dimensions, so the evolution
of journalistic style can be compared across publications and eras.

Design rules:
  - Word lists are identical across all sources (English only).
  - Per-article computations and aggregation are identical across all sources.
  - Each source supplies an iterator yielding (year, month, text) tuples.
  - An OCR-quality metric (stopword density) is emitted alongside the style
    metrics so noisy months can be down-weighted or masked at display time.

Article filter (applied here, not in per-source wrappers):
  - text non-empty
  - word_count >= MIN_WORDS (default 50)
  - digit_ratio < MAX_DIGIT_RATIO (default 0.15)

Schema written by aggregate_monthly:
  {
    "dates":   ["1888-01", "1888-02", ...],
    "metrics": {
      "<key>": {"label": "<human label>", "values": [float|None per date]}
    }
  }
"""

import re
import numpy as np
from collections import defaultdict


# ── Word lists (parallel to build_imm_style.py — keep in sync) ──

FORWARD_WORDS = [
    'will', 'shall', 'expect', 'expected', 'anticipate', 'forecast',
    'prospect', 'outlook', 'future', 'forthcoming', 'propose', 'intend',
    'plan', 'project', 'proposed', 'forward', 'predict', 'probable',
    'likely', 'foresee',
]

BACKWARD_WORDS = [
    'past', 'previous', 'formerly', 'preceding', 'prior', 'retrospect',
    'historical', 'hitherto', 'earlier', 'last', 'recent', 'recently',
    'already',
]

HEDGE_WORDS = [
    'may', 'might', 'perhaps', 'possibly', 'probably', 'approximately',
    'somewhat', 'apparently', 'seemingly', 'uncertain', 'presumably',
]

ANALYTICAL_WORDS = [
    'therefore', 'consequently', 'because', 'owing', 'cause', 'caused',
    'reason', 'result', 'resulting', 'hence', 'thus', 'accordingly',
    'due', 'necessarily',
]

DESCRIPTIVE_WORDS = [
    'reported', 'announced', 'showed', 'noted', 'observed', 'states',
    'states', 'declared', 'mentioned',
]

ATTRIBUTION_WORDS = [
    'according', 'said', 'reportedly', 'sources', 'reports', 'quoted',
    'statement', 'confirmed', 'announced', 'spokesman', 'spokeswoman',
]

PERSON_WORDS = [
    'chairman', 'president', 'director', 'minister', 'sir', 'lord',
    'mr', 'mrs', 'lady', 'governor', 'secretary',
]

EVALUATIVE_WORDS = [
    'excellent', 'strong', 'weak', 'poor', 'unprecedented', 'remarkable',
    'satisfactory', 'unsatisfactory', 'success', 'failure', 'crisis',
    'boom', 'panic', 'disaster', 'critical',
]

# New (FT-extra) — quantifier words
QUANTIFIER_WORDS = [
    'some', 'many', 'few', 'all', 'every', 'several', 'most', 'much',
    'less', 'more', 'none', 'any', 'each', 'numerous', 'majority',
    'minority', 'half', 'nearly',
]

CONFLICT_WORDS = [
    'crisis', 'panic', 'war', 'battle', 'fight', 'struggle', 'dispute',
    'collapse', 'crash', 'failure', 'fail', 'failed', 'attack', 'threat',
    'conflict', 'opposed',
]

CAUSATION_WORDS = [
    'because', 'due', 'cause', 'caused', 'reason', 'consequently',
    'therefore', 'thus', 'hence', 'result', 'led', 'following',
    'owing', 'attributable',
]

MORAL_WORDS = [
    'fraud', 'corrupt', 'corruption', 'honest', 'honour', 'dishonour',
    'wrong', 'just', 'unjust', 'duty', 'responsibility', 'virtue',
    'scandal', 'integrity',
]

METAPHOR_WORDS = [
    'flood', 'flooded', 'tide', 'wave', 'storm', 'plunge', 'plunged',
    'soar', 'soared', 'rocket', 'rocketed', 'tumble', 'tumbled',
    'avalanche', 'tornado',
]

SUSPENSE_WORDS = [
    'await', 'awaiting', 'pending', 'tomorrow', 'uncertain', 'unknown',
    'whether', 'depends', 'expected', 'shortly', 'soon',
]

QUOTATION_REPORTING_VERBS = ['said', 'says', 'stated', 'told']


# ── OCR-quality reference: 30 most common English function words ──
# Robust signal because (a) extremely high frequency in any genuine English
# prose, and (b) the words are short and visually distinctive so OCR usually
# recovers them. Clean prose runs ~25–35% stopword density.
STOPWORDS = frozenset([
    'the', 'of', 'and', 'to', 'in', 'a', 'is', 'that', 'for', 'it',
    'with', 'as', 'on', 'by', 'at', 'this', 'from', 'but', 'not', 'are',
    'or', 'an', 'be', 'was', 'were', 'have', 'has', 'had', 'will', 'would',
])


# ── Filter thresholds (parallel to IMM) ──
MIN_WORDS = 50
MAX_DIGIT_RATIO = 0.15


# ── Helpers ──

_WORD_RE = re.compile(r"[A-Za-z']+")


def digit_ratio(text):
    if not text:
        return 0.0
    digits = sum(1 for c in text if c.isdigit())
    return digits / len(text)


def count_words(text, word_list):
    """Count exact word occurrences (case-insensitive, whole word)."""
    text_lower = text.lower()
    n = 0
    for word in word_list:
        n += len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
    return n


def count_quotes(text):
    return text.count('"') + text.count('“') + text.count('”')


def count_historical_years(text, page_year):
    """Count year-references > 2 years older than the page's own year."""
    if page_year is None:
        return 0
    threshold = page_year - 2
    matches = re.findall(r'\b(\d{4})\b', text)
    return sum(1 for m in matches if 1600 <= int(m) <= threshold)


def count_number_tokens(text):
    """Raw count of integer-like tokens (used by numbers_per_article)."""
    return len(re.findall(r'\b\d+\b', text))


def alpha_tokens(text):
    """Lowercased alphabetic tokens — used for word-length stats and OCR quality."""
    return [t.lower() for t in _WORD_RE.findall(text)]


def word_count_of(text):
    """Plain whitespace-tokenized word count (mirrors IMM's stored word_count)."""
    return len(text.split())


def ocr_quality_score(tokens):
    """Stopword density. Clean prose ~0.25–0.35; OCR-shredded <0.10."""
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in STOPWORDS)
    return hits / len(tokens)


# ── Per-article metric computation ──

def compute_style_metrics(text, wc):
    """Returns dict of 10 style metrics + ocr_quality, or None if too short."""
    if wc < MIN_WORDS:
        return None

    forward = count_words(text, FORWARD_WORDS)
    backward = count_words(text, BACKWARD_WORDS)
    temporal = forward + backward

    hedge = count_words(text, HEDGE_WORDS)
    analytical = count_words(text, ANALYTICAL_WORDS)
    hedge_denom = hedge + analytical

    descriptive = count_words(text, DESCRIPTIVE_WORDS)
    anal_denom = analytical + descriptive

    a_tokens = alpha_tokens(text)
    n_alpha = len(a_tokens)
    if n_alpha == 0:
        return None

    avg_len = sum(len(t) for t in a_tokens) / n_alpha
    long_frac = sum(1 for t in a_tokens if len(t) >= 7) / n_alpha

    return {
        'forward_ratio': forward / temporal if temporal > 0 else 0.5,
        'hedge_ratio': hedge / hedge_denom if hedge_denom > 0 else 0.5,
        'analytical_ratio': analytical / anal_denom if anal_denom > 0 else 0.5,
        'attribution_per_article': count_words(text, ATTRIBUTION_WORDS) / wc * 1000,
        'person_per_article': count_words(text, PERSON_WORDS) / wc * 1000,
        'evaluative_per_article': count_words(text, EVALUATIVE_WORDS) / wc * 1000,
        'quant_per_article': count_words(text, QUANTIFIER_WORDS) / wc * 1000,
        'numbers_per_article': count_number_tokens(text),
        'avg_word_length': avg_len,
        'long_word_frac': long_frac,
        'ocr_quality': ocr_quality_score(a_tokens),
    }


def compute_narrative_metrics(text, wc, year):
    """Returns dict of 7 narrative metrics, or None if too short."""
    if wc < MIN_WORDS:
        return None
    quotes = count_quotes(text)
    reporting = count_words(text, QUOTATION_REPORTING_VERBS)
    return {
        'conflict': count_words(text, CONFLICT_WORDS) / wc * 1000,
        'causation': count_words(text, CAUSATION_WORDS) / wc * 1000,
        'moral': count_words(text, MORAL_WORDS) / wc * 1000,
        'metaphor': count_words(text, METAPHOR_WORDS) / wc * 1000,
        'suspense': count_words(text, SUSPENSE_WORDS) / wc * 1000,
        'quotation': (quotes + reporting) / wc * 1000,
        'historical_memory': count_historical_years(text, year) / wc * 1000,
    }


# ── Article filter ──

def passes_filter(text, wc):
    if not text or wc < MIN_WORDS:
        return False
    if digit_ratio(text) >= MAX_DIGIT_RATIO:
        return False
    return True


# ── Metric labels (mirror website's STYLE_LABELS / NARRATIVE_LABELS) ──

STYLE_LABELS = {
    'forward_ratio': 'Forward-Looking %',
    'hedge_ratio': 'Epistemic Hedging %',
    'analytical_ratio': 'Analytical %',
    'attribution_per_article': 'Attribution / Article',
    'person_per_article': 'Personalization / Article',
    'evaluative_per_article': 'Evaluative / Article',
    'quant_per_article': 'Quantifiers / Article',
    'numbers_per_article': 'Numbers / Article',
    'avg_word_length': 'Avg Word Length',
    'long_word_frac': 'Long-Word Fraction',
    'ocr_quality': 'OCR Text Quality',
}

NARRATIVE_LABELS = {
    'conflict': 'Conflict & Tension',
    'causation': 'Causal Explanation',
    'moral': 'Moral Judgment',
    'metaphor': 'Market Metaphor',
    'suspense': 'Suspense & Uncertainty',
    'quotation': 'Direct Quotation',
    'historical_memory': 'Historical Year References / Article',
}


# ── Monthly aggregation ──

def aggregate_monthly(article_iter, log=print):
    """
    article_iter yields (year:int, month:int, text:str).

    Returns (style_output, narrative_output) — JSON-ready dicts in the
    schema the website expects.
    """
    style_monthly = defaultdict(lambda: defaultdict(list))
    narrative_monthly = defaultdict(lambda: defaultdict(list))

    seen = 0
    kept = 0
    for year, month, text in article_iter:
        seen += 1
        if not (1 <= month <= 12):
            continue
        wc = word_count_of(text)
        if not passes_filter(text, wc):
            continue
        kept += 1
        ym = f"{year:04d}-{month:02d}"

        sm = compute_style_metrics(text, wc)
        if sm:
            for k, v in sm.items():
                style_monthly[ym][k].append(v)

        nm = compute_narrative_metrics(text, wc, year)
        if nm:
            for k, v in nm.items():
                narrative_monthly[ym][k].append(v)

    log(f"  Articles seen: {seen:,}; kept after filter: {kept:,}")

    style_months = sorted(style_monthly.keys())
    narrative_months = sorted(narrative_monthly.keys())

    style_out = {'dates': style_months, 'metrics': {}}
    for k, label in STYLE_LABELS.items():
        vals = []
        for m in style_months:
            v = style_monthly[m].get(k, [])
            vals.append(float(np.mean(v)) if v else None)
        style_out['metrics'][k] = {'label': label, 'values': vals}

    narrative_out = {'dates': narrative_months, 'metrics': {}}
    for k, label in NARRATIVE_LABELS.items():
        vals = []
        for m in narrative_months:
            v = narrative_monthly[m].get(k, [])
            vals.append(float(np.mean(v)) if v else None)
        narrative_out['metrics'][k] = {'label': label, 'values': vals}

    return style_out, narrative_out
