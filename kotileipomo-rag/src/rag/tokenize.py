import re
import unicodedata as _ud
from typing import Iterable, List

STOPWORDS = {
    # English
    "the","a","an","and","or","to","of","for","on","in","is","it","are","do","you","we","i",
    "can","with","at","my","our","your","me","us","be","have","has","will","from","about",
    "what","which","where","when","who","whom","whose","how",
    # Finnish (tiny)
    "ja","tai","se","ne","että","kuin","minun","meidän","teidän","sinun","oma","olen","ovat",
}

def normalize(text: str) -> str:
    t = (text or "").lower().strip()
    t = re.sub(r"[^\w\s\-]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t

def strip_accents(s: str) -> str:
    norm = _ud.normalize("NFD", s)
    return "".join(ch for ch in norm if _ud.category(ch) != "Mn")

def stem_token(tok: str) -> str:
    w = tok
    fi_suf = [
        "hinsa","hänsä","nsä","mme","nne",
        "issaan","issä","issa","istä","ista","isiin","ihin","iin","een",
        "ssa","ssä","sta","stä","lla","llä","lta","ltä","lle",
        "na","nä","ksi","tta","ttä","kin",
        "ita","itä","ien","jen","ja","jä",
        "t","n","a","ä",
    ]
    for sfx in sorted(fi_suf, key=len, reverse=True):
        if w.endswith(sfx) and len(w) - len(sfx) >= 3:
            w = w[: -len(sfx)]
            break
    sv_suf = ["arnas","ernas","ornas","andes","endes","arna","erna","orna","heten","ande","ende","en","et","na","ar","er","or","n","s"]
    for sfx in sorted(sv_suf, key=len, reverse=True):
        if w.endswith(sfx) and len(w) - len(sfx) >= 3:
            w = w[: -len(sfx)]
            break
    if w.endswith("'s") and len(w) > 3:
        w = w[:-2]
    elif w.endswith("es") and len(w) > 4:
        w = w[:-2]
    elif w.endswith("s") and len(w) > 3:
        w = w[:-1]
    return w

def tokens(text: str) -> Iterable[str]:
    for tok in normalize(text).split():
        if tok in STOPWORDS:
            continue
        base = tok
        stem = stem_token(base)
        yielded = set()
        for v in (base, stem, strip_accents(base), strip_accents(stem)):
            if v and v not in yielded:
                yielded.add(v)
                yield v

def tokenize_list(text: str) -> List[str]:
    return list(tokens(text))

