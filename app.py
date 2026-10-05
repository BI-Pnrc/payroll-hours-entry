import re
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from chat_parser import parse_block, PAY_TYPES
from matcher import match_names

MIN_SCORE = 0.85   # name similarity needed to auto-match when no employee ID is given


def find_ids_in_text(df, master):
    """If a pasted line contains a known employee ID (e.g. E003), use it."""
    ids = set(master['employee_id'])
    found = []
    for raw in df['name_raw']:
        tokens = re.findall(r'[A-Za-z0-9_-]+', str(raw))
        found.append(next((t for t in tokens if t in ids), ''))
    return found


def build_table(text, master):
    parsed = parse_block(text)
    if parsed.empty:
        return parsed
    res = match_names(parsed, master)
    text_ids = find_ids_in_text(res, master)
    res['employee_id'] = [
        t or (i if s >= MIN_SCORE else '')
        for t, i, s in zip(text_ids, res['employee_id'], res['score'])
    ]
    res['chat_hours'] = res['hours']
    return res[['name_raw', 'employee_id', 'pay_type', 'hours', 'chat_hours', 'flags']]


def add_lookup_and_status(df, master):
    """Look up the master name from employee_id and set Matched / Not matched."""
    out = df.copy()
    names = master.set_index('employee_id')['employee_name']
    out['employee_name'] = out['employee_id'].map(names).fillna('')

    dup = out.duplicated(subset=['employee_id', 'pay_type'], keep=False) & (out['employee_id'] != '')
    status = []
    for i, row in out.iterrows():
        hours, chat = row['hours'], row['chat_hours']
        ok = (
            row['employee_name'] != ''
            and pd.notna(hours) and hours > 0
            and pd.notna(chat) and abs(float(hours) - float(chat)) < 1e-9
            and not dup[i]
        )
        status.append('Matched' if ok else 'Not matched')
    out['status'] = status
    return out[['name_raw', 'employee_id', 'employee_name', 'pay_type', 'hours', 'chat_hours',
                'status', 'flags']]


def editor_key():
    return f"editor_{st.session_state.get('version', 0)}"


def apply_edits(master):
    """Callback: copy the user's edits into the stored table and re-check it."""
    df = st.session_state['base'].copy()
    for idx, changes in st.session_state[editor_key()]['edited_rows'].items():
        for col, val in changes.items():
            df.loc[idx, col] = val if val is not None else ('' if col != 'hours' else None)
    st.session_state['base'] = add_lookup_and_status(
        df[['name_raw', 'employee_id', 'pay_type', 'hours', 'chat_hours', 'flags']], master)


def to_excel(df, period):
    out = pd.DataFrame({
        'period_end': period.strftime('%Y-%m-%d'),
        'employee_id': df['employee_id'].values,
        'employee_name': df['employee_name'].values,
        'pay_type': df['pay_type'].values,
        'hours': df['hours'].values,
    })
    buf = BytesIO()
    out.to_excel(buf, index=False)
    return buf.getvalue()


st.set_page_config(page_title='Payroll Hours Entry', layout='wide')
st.title('Payroll Hours Entry')

def clean_master(df):
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
    df = df[['employee_id', 'employee_name']].astype(str)
    df = df.apply(lambda c: c.str.strip())
    df = df[(df['employee_id'] != '') & (df['employee_id'] != 'nan')]
    return df.drop_duplicates('employee_id').reset_index(drop=True)


def check_password():
    """Optional team password: only enforced if APP_PASSWORD is set in Streamlit secrets."""
    try:
        pw = st.secrets.get('APP_PASSWORD', '')
    except Exception:
        pw = ''
    if not pw or st.session_state.get('authed'):
        return
    entered = st.text_input('Password', type='password')
    if entered and entered == pw:
        st.session_state['authed'] = True
        st.rerun()
    elif entered:
        st.error('Wrong password.')
    st.stop()


check_password()

if 'master' not in st.session_state:
    st.session_state['master'] = pd.DataFrame(columns=['employee_id', 'employee_name'])

with st.sidebar:
    st.header('Employee list')
    st.caption('Kept only for this browser session. Nothing is stored on the server.')
    up = st.file_uploader('Upload employee list (CSV or Excel with employee_id, employee_name)',
                          type=['csv', 'xlsx'])
    if up is not None and st.button('Use uploaded file'):
        try:
            raw = pd.read_csv(up, dtype=str) if up.name.lower().endswith('.csv')                 else pd.read_excel(up, dtype=str)
            st.session_state['master'] = clean_master(raw)
            st.rerun()
        except Exception:
            st.error('Could not read the file. It needs employee_id and employee_name columns.')
    edited = st.data_editor(st.session_state['master'], num_rows='dynamic', hide_index=True,
                            key='master_editor', width='stretch')
    if st.button('Apply changes'):
        st.session_state['master'] = clean_master(edited.fillna(''))
        st.rerun()

master = st.session_state['master']
if master.empty:
    st.info('Upload your employee list in the sidebar (or add employees there) to get started.')
    st.stop()

period = st.date_input('Pay period end (FE date)', value=date.today())
text = st.text_area('Paste the client chat/email text here', height=220)

if st.button('Create table'):
    if not text.strip():
        st.warning('Please paste the text first.')
    else:
        table = build_table(text, master)
        if table.empty:
            st.warning('Nothing could be read from the text.')
            st.session_state.pop('base', None)
        else:
            st.session_state['version'] = st.session_state.get('version', 0) + 1
            st.session_state['base'] = add_lookup_and_status(table, master)

if 'base' in st.session_state:
    df = st.session_state['base']
    st.subheader('Review')
    st.caption('Full names come from your employee list. A row is Matched when the employee is found '
               'and Hours equals Hours in chat. If not, pick the right employee ID in the table.')

    st.data_editor(
        df,
        hide_index=True,
        key=editor_key(),
        on_change=apply_edits,
        args=(master,),
        disabled=['name_raw', 'employee_name', 'chat_hours', 'status', 'flags'],
        column_config={
            'name_raw': 'Name in chat',
            'employee_id': st.column_config.SelectboxColumn(
                'employee_id', options=[''] + master['employee_id'].tolist()),
            'pay_type': st.column_config.SelectboxColumn(
                'pay_type', options=[''] + PAY_TYPES),
            'hours': st.column_config.NumberColumn('hours', min_value=0.0),
            'chat_hours': 'Hours in chat',
            'flags': None,
        },
    )

    bad = int((df['status'] != 'Matched').sum())
    st.write(f"Matched: {len(df) - bad}  |  Not matched: {bad}")
    if bad:
        st.info('Export is available once every row is Matched.')
    st.download_button(
        'Export to Excel',
        data=to_excel(df, period),
        file_name=f"Payroll_Hours_{period.strftime('%Y-%m-%d')}.xlsx",
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        disabled=bool(bad),
    )
