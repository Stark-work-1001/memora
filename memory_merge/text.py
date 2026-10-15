"""Text handling: normalization, the lexical analyzer behind FTS5, secret screening, redaction.

Why the analyzer lives in Python: FTS5's unicode61 tokenizer only splits on whitespace and
punctuation, so an unspaced Chinese sentence becomes one giant token and is effectively unsearchable.
A custom FTS5 tokenizer needs a loadable C extension, which several Python builds disable. Instead we
pre-segment text into space-separated terms -- runs of unspaced scripts become overlapping bigrams,
the scheme of Lucene's CJKBigramFilter -- and let unicode61 split on our spaces. Queries go through
the same code, so index and query cannot disagree. ANALYZER is stored in the database; changing the
scheme forces an index rebuild instead of a silent mismatch.
"""
import hashlib
import math
import re
import unicodedata

ANALYZER = 'mm-bigram-1'

# Scripts written without spaces between words (plus Hangul, whose particles attach to words).
_NOSPACE = (
    (0x0E00, 0x0EFF),    # Thai, Lao
    (0x1000, 0x109F),    # Myanmar
    (0x1100, 0x11FF),    # Hangul Jamo
    (0x1780, 0x17FF),    # Khmer
    (0x2E80, 0x2FDF),    # CJK radicals
    (0x3005, 0x3007),    # 々 〆 〇
    (0x3040, 0x30FA),    # Hiragana, Katakana (U+30FB middle dot is punctuation)
    (0x30FC, 0x30FF),
    (0x3130, 0x318F),    # Hangul compatibility Jamo
    (0x31F0, 0x31FF),
    (0x3400, 0x4DBF),    # CJK extension A
    (0x4E00, 0x9FFF),    # CJK unified ideographs
    (0xAC00, 0xD7AF),    # Hangul syllables
    (0xF900, 0xFAFF),    # CJK compatibility ideographs
    (0x20000, 0x323AF),  # CJK extensions B..H
)

# Query-side only: bigrams made purely of these function characters carry no topic signal
# ("是什", "什么"). The index keeps everything, so this list can be retuned without a rebuild.
# Query-side English function words, for the same reason: under OR semantics 'where does its'
# matches every English memory. Removed from queries only, never from the index.
STOP_WORDS = set(('a an the is are was were be been being am do does did done doing have has had having of to in on at by for '
                  'from with about into onto over under than then as and or but if so not no nor it its this that these those '
                  'there here what which who whom whose when where why how i me my we us our you your he him his she her they '
                  'them their can could should would will shall may might must any some all each every also just very').split())
STOP_CHARS = set('的了是在和与及或吗呢吧啊么什怎哪谁这那个也都就而被把着过之其为以于对从但所如若则即该此每各有没不要会能可还又再很更最')


def is_nospace(ch):
    cp = ord(ch)
    for lo, hi in _NOSPACE:
        if lo <= cp <= hi: return True
    return False


def _is_word(ch):
    return ch == '_' or unicodedata.category(ch)[0] in 'LNM'


def normalize(text):
    """NFKC folds full-width forms; casefold handles case beyond ASCII."""
    return unicodedata.normalize('NFKC', text).casefold()


def runs(text):
    """Yield ('cjk', run) for unspaced-script runs and ('word', run) for other word characters.

    Splitting at script boundaries is what makes '选择SQLite作为真源' searchable for 'sqlite'.
    """
    kind, buf = None, []
    for ch in normalize(text):
        k = 'cjk' if is_nospace(ch) else ('word' if _is_word(ch) else None)
        if k != kind and buf:
            yield kind, ''.join(buf); buf = []
        kind = k
        if k: buf.append(ch)
    if buf and kind: yield kind, ''.join(buf)


def bigrams(run):
    return [run] if len(run) < 2 else [run[i:i + 2] for i in range(len(run) - 1)]


def analyze(text):
    """Document analysis -> (terms, chars) strings for the two FTS columns.

    terms: words plus CJK bigrams. chars: CJK unigrams, in their own column so single-character
    queries work without unigrams inflating the length normalisation of the main column.
    """
    terms, chars = [], []
    for kind, run in runs(text):
        if kind == 'word':
            terms.append(run)
        else:
            terms.extend(bigrams(run)); chars.extend(run)
    return ' '.join(terms), ' '.join(chars)


def _quote(term):
    return '"' + term.replace('"', '""') + '"'


# Chosen on the dev split of datasets/memory-eval-v1 (docs/EVALUATION.md); test split not consulted.
QUERY_DEFAULTS = {'stop_chars': True, 'stop_words': True, 'unigrams': True, 'prefix': True}


def query_terms(text, stop_chars=True, unigrams=True, stop_words=True, prefix=True, max_terms=96):
    """Analyse a query into FTS5 phrases [(column or None, term)], segmented exactly like analyze().

    prefix=True also matches Latin words by prefix ('lint' -> 'linter'); docs/EVALUATION.md records
    whether that helps. Returns [] if every term was a stop term; callers then retry without stops.
    """
    out, seen = [], set()
    def add(col, term):
        if (col, term) not in seen and len(out) < max_terms:
            seen.add((col, term)); out.append((col, term))
    for kind, run in runs(text):
        if kind == 'word':
            if stop_words and run in STOP_WORDS: continue
            add(None, run)
            if prefix and len(run) >= 3 and not run.isdigit(): add('prefix', run)
        elif len(run) == 1:
            add('chars', run)
        else:
            for bg in bigrams(run):
                if not (stop_chars and bg[0] in STOP_CHARS and bg[1] in STOP_CHARS): add('terms', bg)
            if unigrams:
                for ch in run:
                    if ch not in STOP_CHARS: add('chars', ch)
    return out


def fts_query(terms):
    """OR of quoted phrases; quoting makes user input inert as FTS5 syntax."""
    return ' OR '.join(_quote(t) + ' *' if col == 'prefix' else (col + ' : ' if col else '') + _quote(t) for col, t in terms)


def norm_digest(text):
    """Digest for duplicate detection: insensitive to width, case and whitespace."""
    return hashlib.sha256(' '.join(normalize(text).split()).encode()).hexdigest()


def digest(text):
    """Content digest exactly as 0.1 computed it; vectors and judgements are keyed on it."""
    return hashlib.sha256(text.encode()).hexdigest()


def estimate_tokens(text):
    """Model-agnostic estimate: ~1 token per CJK character, ~4 characters per token otherwise.

    Deliberately an estimate: exact counts need the client's tokenizer, which we do not know.
    """
    cjk = sum(1 for ch in text if is_nospace(ch))
    return cjk + math.ceil((len(text) - cjk) / 4)


# --- secret screening -------------------------------------------------------------------------
# Patterns name the *kind* of secret; matched text is never logged or returned.
_Q = '["\u0027]?'  # optional quote around keys/values in config-like text
_VALUE = '([^\\s"\u0027,;]{6,})'
_SECRETS = [
    # key = value pairs are flagged only when the value looks like a secret (see _looks_secret), so a
    # note *about* passwords ("passwords live in the team password manager") is not rejected.
    ('assignment', r'(?i)\b(?:api[_-]?key|apikey|passw(?:or)?d|pwd|secret|client[_-]?secret|access[_-]?token|auth[_-]?token|refresh[_-]?token|private[_-]?key)\b' + _Q + r'\s*[:=]\s*' + _Q + _VALUE),
    ('assignment_zh', r'(?:密码|口令|密钥|令牌|秘钥)\s*(?:是|为|[:：=])\s*([A-Za-z0-9!@#$%^&*()_+=./?~-]{6,})'),
    ('private_key', r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    ('provider_key', r'\bsk-(?:proj-|ant-(?:api\d+-)?)?[A-Za-z0-9_-]{16,}'),
    ('github_token', r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    ('aws_access_key', r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b'),
    ('slack_token', r'\bxox[abprs]-[A-Za-z0-9-]{10,}'),
    ('google_api_key', r'\bAIza[0-9A-Za-z_-]{35}\b'),
    ('jwt', r'\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}'),
    ('bearer_token', r'(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}'),
    ('url_credentials', r'(?i)\b[a-z][a-z0-9+.-]*://[^:/@\s]+:[^@/\s]{3,}@'),
]
_VALUE_CHECKED = {'assignment', 'assignment_zh'}
_SECRET_RES = [(k, re.compile(p)) for k, p in _SECRETS]
_CARD = re.compile(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)')


# Exact shapes only: anything merely *containing* 'env' or starting with '$' could be a real password.
_PLACEHOLDER = re.compile(r'^(?:\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|<[A-Za-z_][A-Za-z0-9_ -]*>|%[A-Za-z_][A-Za-z0-9_]*%'
                          r'|\{\{\s*[\w.]+\s*\}\}|\*+|x+|X+|\.{3,}|(?:REDACTED|CHANGEME|changeme|your[-_]?\w+))$')
_REFERENCE = re.compile(r'^(?:os\.environ|os\.getenv|process\.env|getenv\(|env\(|ENV\[|System\.getenv|secrets\.)', re.I)


def _looks_secret(v):
    """After 'password =' a value is a secret unless it is a placeholder or a reference to where the
    secret lives: '<API_KEY>', '$DB_PASSWORD', '${TOKEN}', '%TOKEN%', 'os.environ[...' are not;
    'hunter2pass', 'supersecret123', '$uperS3cret!', 'Envoy#2024xyz' and any 24+ character run are.
    A plain word ('rotated') is not, so notes *about* passwords are not rejected."""
    if _PLACEHOLDER.match(v) or _REFERENCE.match(v): return False
    if len(v) >= 24: return True
    return (any(c.isdigit() for c in v) or any(not c.isalnum() and c not in '-_.' for c in v)
            or (any(c.isupper() for c in v[1:]) and any(c.islower() for c in v)))


def _luhn(digits):
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n *= 2
            if n > 9: n -= 9
        total += n; alt = not alt
    return total % 10 == 0


def find_secrets(text):
    """Return [(kind, start, end)] for likely credentials and payment card numbers in `text`."""
    hits = [(k, m.start(), m.end()) for k, rx in _SECRET_RES for m in rx.finditer(text)
            if k not in _VALUE_CHECKED or _looks_secret(m.group(1))]
    for m in _CARD.finditer(text):
        digits = re.sub(r'\D', '', m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits): hits.append(('payment_card', m.start(), m.end()))
    return sorted(hits, key=lambda h: (h[1], -h[2]))


def secret_kinds(text):
    """Kinds of secrets in the text or in its NFKC form (full-width 'ａｐｉ＿ｋｅｙ＝…' must not slip through)."""
    folded = unicodedata.normalize('NFKC', text)
    return sorted({h[0] for h in find_secrets(text)} | ({h[0] for h in find_secrets(folded)} if folded != text else set()))


def _redact_spans(text):
    hits = find_secrets(text)
    if not hits: return text, []
    merged = []  # union overlapping spans so no fragment of a secret survives
    for kind, start, end in hits:
        if merged and start < merged[-1][2]:
            merged[-1][2] = max(merged[-1][2], end)
        else:
            merged.append([kind, start, end])
    out, pos = [], 0
    for kind, start, end in merged:
        out.append(text[pos:start]); out.append(f'[REDACTED:{kind}]'); pos = end
    out.append(text[pos:])
    return ''.join(out), [m[0] for m in merged]


def redact(text):
    """Replace detected secrets with [REDACTED:kind] -> (text, kinds).

    Used for bulk imports, where rejecting a whole document or session over one token would be
    worse than masking it. Single memories are rejected instead, so the writer redacts knowingly.
    If only the NFKC form reveals a secret, the NFKC form is redacted and returned.
    """
    out, kinds = _redact_spans(text)
    folded = unicodedata.normalize('NFKC', out)
    if folded != out and find_secrets(folded):
        out, more = _redact_spans(folded); kinds += more
    return out, kinds


def redact_value(value):
    """Redact every string inside a JSON-like value (locators, titles, metadata). -> (value, count)."""
    if isinstance(value, str):
        out, kinds = redact(value); return out, len(kinds)
    if isinstance(value, list):
        pairs = [redact_value(v) for v in value]; return [p[0] for p in pairs], sum(p[1] for p in pairs)
    if isinstance(value, dict):
        pairs = {k: redact_value(v) for k, v in value.items()}; return {k: p[0] for k, p in pairs.items()}, sum(p[1] for p in pairs.values())
    return value, 0


# --- prompt-injection markers -------------------------------------------------------------------
# A heuristic flag for reviewers and evidence packs, never a filter: legitimate procedures are
# imperative too ("always run tests before tagging"), so blocking on this would destroy real data.
_INJECTION = re.compile('|'.join([
    r'\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier|all|system)\b[^.\n]{0,20}\b(?:instructions?|prompts?|rules?|messages?)',
    r'\byou are now\b', r'\bnew (?:system )?instructions?\s*:', r'\bsystem prompt\b',
    r'</?\s*(?:system|assistant|instructions?)\s*>', r'<\|im_(?:start|end)\|>', r'^\s*(?:system|assistant)\s*:',
    r'(?:忽略|无视|忘记|忘掉)[^。\n]{0,12}(?:之前|以上|上面|前面|先前|所有|全部)[^。\n]{0,12}(?:指令|指示|提示|规则|要求|说明)',
    r'(?:你现在是|从现在起你是|新的指令[:：])',
]), re.I | re.M)


def instruction_like(text):
    return bool(_INJECTION.search(text))
