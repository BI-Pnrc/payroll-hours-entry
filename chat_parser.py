import re
import pandas as pd

HOURS_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:hrs?|hours?)\b', re.I)
PAY_TYPES = ['ordinary', 'overtime', 'saturday', 'sunday', 'public holiday']


def parse_block(text):
    rows, names = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = HOURS_RE.search(line)
        if m:  # hours wali line
            hours = float(m.group(1))
            rest = HOURS_RE.sub('', line).lower()
            pay = next((p for p in PAY_TYPES if p in rest), '')
            flags = []
            if not names:
                flags.append('NO_NAME')
            if len(names) > 1:
                flags.append('SHARED_HOURS_CHECK')
            if not pay:
                flags.append('NO_PAY_TYPE')
            for n in (names or ['']):
                rows.append({'name_raw': n, 'pay_type': pay,
                             'hours': hours, 'flags': ', '.join(flags)})
            names = []
        else:  # naam wali line
            names.append(line)
    for n in names:
        rows.append({'name_raw': n, 'pay_type': '', 'hours': None,
                     'flags': 'NAME_WITHOUT_HOURS'})
    return pd.DataFrame(rows)


if __name__ == '__main__':
    with open('sample_input.txt', encoding='utf-8') as f:
        df = parse_block(f.read())
    print(df.to_string(index=False))
