import difflib
import pandas as pd
from chat_parser import parse_block


def norm(s):
    return ' '.join(str(s).lower().split())


def _token_score(raw_tokens, master_tokens):
    """How well every word of the chat name is found in a master name.
    First-name-only, last-name-only and partial names all work (typos tolerated)."""
    used, total = set(), 0.0
    for rt in raw_tokens:
        best, best_j = 0.0, None
        for j, mt in enumerate(master_tokens):
            if j in used:
                continue
            r = 1.0 if rt == mt else difflib.SequenceMatcher(None, rt, mt).ratio()
            if r > best:
                best, best_j = r, j
        if best < 0.8:
            return 0.0
        used.add(best_j)
        total += best
    return total / len(raw_tokens)


def _best_match(k, master):
    """Return (row_index, score, ambiguous) for a normalised chat name."""
    raw_tokens = k.split()
    scored = []
    for i, mk in enumerate(master['key']):
        s = _token_score(raw_tokens, mk.split())
        if s > 0:
            scored.append((s, i))
    if not scored:
        best = difflib.get_close_matches(k, master['key'].tolist(), n=1, cutoff=0.6)
        if not best:
            return None, 0, False
        i = master.index[master['key'] == best[0]][0]
        return i, difflib.SequenceMatcher(None, k, best[0]).ratio(), False
    scored.sort(reverse=True)
    top = scored[0][0]
    ties = [i for s, i in scored if abs(s - top) < 1e-9]
    if len(ties) > 1:   # e.g. "Singh" matches several employees -> user must pick
        return None, 0, True
    return scored[0][1], top, False


def match_names(df, master):
    master = master.copy().reset_index(drop=True)
    master['key'] = master['employee_name'].map(norm)

    ids, matched, scores, new_flags = [], [], [], []
    for raw, old in zip(df['name_raw'], df['flags']):
        k = norm(raw)
        flags = [f for f in old.split(', ') if f]
        i, score, ambiguous = _best_match(k, master) if k else (None, 0, False)
        if i is not None:
            row = master.loc[i]
            ids.append(row['employee_id'])
            matched.append(row['employee_name'])
            scores.append(round(score, 2))
            if k != row['key']:
                flags.append('PARTIAL_OR_FUZZY_MATCH_CHECK')
        else:
            ids.append('')
            matched.append('')
            scores.append(0)
            if ambiguous:
                flags.append('AMBIGUOUS_NAME')
            elif k:
                flags.append('NAME_NOT_FOUND')
        new_flags.append(', '.join(flags))

    out = df.copy()
    out['employee_id'] = ids
    out['matched_name'] = matched
    out['score'] = scores
    out['flags'] = new_flags
    return out[['name_raw', 'employee_id', 'matched_name', 'score',
                'pay_type', 'hours', 'flags']]


if __name__ == '__main__':
    with open('sample_input.txt', encoding='utf-8') as f:
        parsed = parse_block(f.read())
    master = pd.read_csv('employee_master.csv')
    print(match_names(parsed, master).to_string(index=False))