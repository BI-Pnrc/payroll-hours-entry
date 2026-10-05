import difflib
import pandas as pd
from chat_parser import parse_block


def norm(s):
    return ' '.join(str(s).lower().split())


def match_names(df, master):
    master = master.copy()
    master['key'] = master['employee_name'].map(norm)
    keys = master['key'].tolist()

    ids, matched, scores, new_flags = [], [], [], []
    for raw, old in zip(df['name_raw'], df['flags']):
        k = norm(raw)
        flags = [f for f in old.split(', ') if f]
        best = difflib.get_close_matches(k, keys, n=1, cutoff=0.6) if k else []
        if best:
            score = difflib.SequenceMatcher(None, k, best[0]).ratio()
            row = master[master['key'] == best[0]].iloc[0]
            ids.append(row['employee_id'])
            matched.append(row['employee_name'])
            scores.append(round(score, 2))
            if score < 1:
                flags.append('FUZZY_MATCH_CHECK')
        else:
            ids.append('')
            matched.append('')
            scores.append(0)
            if k:
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