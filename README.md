# SFA & MFA Orchestrator (Streamlit)

## Run locally

```bash
pip install -r requirements.txt
streamlit run /workspace/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

## Configure
- Base directory defaults to `/workspace/artifacts` (change in the sidebar or set `SFA_MFA_BASE_DIR`).
- Set runners in the sidebar or via env vars:
  - `SFA_RUNNER` (default `your_module:run_sfa`)
  - `MFA_RUNNER` (default `your_module:run_mfa`)

Runners support:
- `module:function` (imported and called with the YAML config path string)
- Shell command with `{config}` placeholder, e.g. `python -m your_module.sfa --config {config}`

## Folder layout per model
```
<base_dir>/
  <model_name>/
    configs/
    data/
    outputs/<process_name_long>/<timestamp>/
    logs/
```