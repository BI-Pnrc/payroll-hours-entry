# Payroll Hours Entry (online)

## Deploy on Streamlit Community Cloud
1. Create a GitHub repo and upload everything in this folder.
2. Go to https://share.streamlit.io -> New app -> pick the repo, main file `app.py`.
3. (Recommended) App settings -> Secrets, add:  `APP_PASSWORD = "choose-a-team-password"`
4. Share the app link with your team.

Each user uploads their own employee list (see `employee_list_template.csv`) every session; nothing is stored on the server.
Note: the repo should be **private** and must not contain real employee data.
