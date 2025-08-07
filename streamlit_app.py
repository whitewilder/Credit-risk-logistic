import os
import sys
from pathlib import Path
from datetime import datetime
import importlib
import traceback
import streamlit as st

# ========== App Config ==========
st.set_page_config(page_title="SFA & MFA Orchestrator", layout="wide")

# ========== Utilities ==========

def get_base_directory() -> Path:
    default_base = Path(os.getenv("SFA_MFA_BASE_DIR", "/workspace/artifacts")).resolve()
    if "base_directory" not in st.session_state:
        st.session_state.base_directory = default_base
    base_dir = Path(st.sidebar.text_input("Base directory", str(st.session_state.base_directory)))
    base_dir.mkdir(parents=True, exist_ok=True)
    st.session_state.base_directory = base_dir
    return base_dir

@st.cache_data(show_spinner=False)
def list_models(base_dir: Path) -> list[str]:
    if not base_dir.exists():
        return []
    return sorted([p.name for p in base_dir.iterdir() if p.is_dir()])

@st.cache_data(show_spinner=False)
def list_outputs(output_dir: Path):
    from glob import glob
    charts = glob(str(output_dir / "**/*.png"), recursive=True)
    tables = glob(str(output_dir / "**/*.csv"), recursive=True)
    excels = glob(str(output_dir / "**/*.xlsx"), recursive=True)
    return charts, tables, excels


def ensure_model_structure(base_dir: Path, model_name: str) -> dict[str, Path]:
    model_root = base_dir / model_name
    configs_dir = model_root / "configs"
    data_dir = model_root / "data"
    outputs_dir = model_root / "outputs"
    logs_dir = model_root / "logs"
    for p in [configs_dir, data_dir, outputs_dir, logs_dir]:
        p.mkdir(parents=True, exist_ok=True)
    return {
        "model_root": model_root,
        "configs_dir": configs_dir,
        "data_dir": data_dir,
        "outputs_dir": outputs_dir,
        "logs_dir": logs_dir,
    }


def default_paths(structure: dict[str, Path], process_name_long: str) -> dict[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config_path = structure["configs_dir"] / f"{process_name_long}.yaml"
    output_run_dir = structure["outputs_dir"] / process_name_long / timestamp
    output_run_dir.mkdir(parents=True, exist_ok=True)
    return {"config_path": config_path, "output_dir": output_run_dir}


def save_yaml(config: dict, path: Path):
    import yaml  # lazy import
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(config, f, default_flow_style=False)


def load_csv_head(csv_path: Path, nrows: int = 1000):
    import pandas as pd  # lazy import
    return pd.read_csv(csv_path, nrows=nrows)


def call_runner(runner_spec: str, config_path: Path) -> tuple[bool, str]:
    """Call a runner specified as 'module:function' or a shell command.
    Returns (success, message)."""
    try:
        if ":" in runner_spec and not runner_spec.strip().startswith(("/", "python", "python3")):
            module_name, func_name = runner_spec.split(":", 1)
            module = importlib.import_module(module_name)
            func = getattr(module, func_name)
            func(str(config_path))
            return True, "Run completed"
        else:
            import subprocess  # lazy
            cmd = runner_spec.format(config=str(config_path))
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                return True, result.stdout
            return False, result.stderr or result.stdout
    except Exception:
        return False, traceback.format_exc()


# ========== Sidebar: Global Settings ==========
base_dir = get_base_directory()
existing_models = list_models(base_dir)

st.sidebar.markdown("### Model")
model_action = st.sidebar.radio("Select action", ["Use existing", "Create new"], horizontal=True)
if model_action == "Use existing" and existing_models:
    model_name = st.sidebar.selectbox("Model folder", existing_models, index=0)
else:
    model_name = st.sidebar.text_input("New model name", value=(existing_models[0] if existing_models else "MyModel"))

structure = ensure_model_structure(base_dir, model_name)

with st.sidebar.expander("Advanced runners", expanded=False):
    sfa_runner = st.text_input(
        "SFA runner (module:function or shell cmd with {config})",
        value=os.getenv("SFA_RUNNER", "your_module:run_sfa"),
        key="sfa_runner",
    )
    mfa_runner = st.text_input(
        "MFA runner (module:function or shell cmd with {config})",
        value=os.getenv("MFA_RUNNER", "your_module:run_mfa"),
        key="mfa_runner",
    )

# ========== Main UI ==========
st.title("SFA & MFA Config Builder, Runner, and Visualizer")

sfa_tab, mfa_tab = st.tabs(["🚀 SFA Flow", "🛠 MFA Runner"])

# -----------------------------
# SFA TAB: Build Config -> Run -> Visualize
# -----------------------------
with sfa_tab:
    st.header("Step 1 — Build SFA Config")

    with st.form("sfa_config_form"):
        process_name = st.text_input("Short process name", value="test_run")
        process_name_long = st.text_input("Long process name", value="Test_Process")
        target_variable = st.text_input("Target variable column", value="target")

        st.subheader("Imputation & Outlier Settings")
        imputation_analysis_segmentors = st.multiselect(
            "Imputation segmentors", ["segment1", "segment2", "segment3"], []
        )
        continuous_imputation_method = st.selectbox(
            "Imputation method", ["mean", "median", "mode"], index=0
        )
        outlier_detection_approach = st.selectbox(
            "Outlier detection", ["grubbs", "local_outlier_factor", "iqr"], index=2
        )
        max_segmentation_levels = st.number_input("Max segmentation levels", 1, 8, 3)
        inplace_imputation = st.checkbox("In-place imputation", value=True)
        gini_delta_threshold = st.number_input("Gini delta threshold", 0.0, 1.0, 0.01)
        kw_p_value_threshold = st.number_input("KW p-value threshold", 0.0, 1.0, 0.05)
        winsorisation_quantiles = st.number_input("Winsorisation quantiles", 1, 100, 20)
        maximum_winsorisation = st.slider("Max winsorisation", 0.0, 1.0, 0.4)

        st.subheader("Run Paths")
        defaults = default_paths(structure, process_name_long)
        data_path_default = structure["data_dir"] / "data.csv"
        variable_config_default = structure["configs_dir"] / "variable_config.xlsx"

        data_csv_upload = st.file_uploader("Upload data.csv", type=["csv"], key="data_csv_upload")
        if data_csv_upload is not None:
            data_path_default.parent.mkdir(parents=True, exist_ok=True)
            with open(data_path_default, "wb") as f:
                f.write(data_csv_upload.getbuffer())
            st.info(f"Saved data to {data_path_default}")

        var_config_upload = st.file_uploader("Upload variable_config.xlsx", type=["xlsx"], key="var_config_upload")
        if var_config_upload is not None:
            variable_config_default.parent.mkdir(parents=True, exist_ok=True)
            with open(variable_config_default, "wb") as f:
                f.write(var_config_upload.getbuffer())
            st.info(f"Saved variable config to {variable_config_default}")

        data_path = Path(st.text_input("Data file path (.csv)", str(data_path_default)))
        variable_config_path = Path(st.text_input("Variable config path (.xlsx)", str(variable_config_default)))
        output_directory_path = Path(st.text_input("Output directory", str(defaults["output_dir"])))

        st.subheader("Run Flags")
        winsorisation_analysis = st.checkbox("Winsorisation analysis", value=True)
        winsorisation_application = st.checkbox("Apply winsorisation", value=True)
        imputation_analysis = st.checkbox("Imputation analysis", value=True)
        imputation_application = st.checkbox("Apply imputation", value=True)

        config_save_path = Path(
            st.text_input("YAML Save Path", str(defaults["config_path"]))
        )

        submitted = st.form_submit_button("Save Config")

        if submitted:
            config = {
                "run_parameters": {
                    "process_name": process_name,
                    "process_name_long": process_name_long,
                    "target_variable": target_variable,
                    "imputation_analysis_segmentors": imputation_analysis_segmentors,
                    "continuous_imputation_method": continuous_imputation_method,
                    "outlier_detection_approach": outlier_detection_approach,
                    "max_segmentation_levels": max_segmentation_levels,
                    "inplace_imputation": inplace_imputation,
                    "gini_delta_threshold": gini_delta_threshold,
                    "kw_p_value_threshold": kw_p_value_threshold,
                    "winsorisation_quantiles": winsorisation_quantiles,
                    "maximum_winsorisation": maximum_winsorisation,
                    "run_paths": {
                        "data_path": str(data_path),
                        "variable_config_path": str(variable_config_path),
                        "output_directory_path": str(output_directory_path),
                    },
                    "run_flags": {
                        "winsorisation_analysis": winsorisation_analysis,
                        "winsorisation_application": winsorisation_application,
                        "imputation_analysis": imputation_analysis,
                        "imputation_application": imputation_application,
                    },
                }
            }
            save_yaml(config, config_save_path)
            st.success(f"YAML saved to {config_save_path}")
            st.session_state["last_config_path"] = str(config_save_path)
            st.session_state["last_output_dir"] = str(output_directory_path)

    st.divider()
    st.header("Step 2 — Run SFA")

    config_to_run = Path(
        st.text_input(
            "Path to config file to run",
            value=st.session_state.get("last_config_path", str(default_paths(structure, "Run")["config_path"])),
        )
    )
    run_col1, run_col2 = st.columns([1, 3])
    with run_col1:
        run_button = st.button("Run SFA now", type="primary")
    with run_col2:
        st.caption("Uses runner from the sidebar. Supports Python import or shell command.")

    if run_button:
        with st.spinner("Running SFA..."):
            ok, msg = call_runner(st.session_state.get("sfa_runner", "your_module:run_sfa"), config_to_run)
        if ok:
            st.success("SFA run completed.")
        else:
            st.error("SFA failed")
            st.code(msg)

    st.divider()
    st.header("Step 3 — Visualize Outputs")

    output_path = Path(
        st.text_input(
            "Enter Output Directory Path",
            value=st.session_state.get("last_output_dir", str(structure["outputs_dir"])),
        )
    )

    if st.button("Load Outputs"):
        charts, tables, excels = list_outputs(output_path)

        max_charts = st.number_input("Max charts to display", min_value=1, max_value=100, value=12)
        csv_preview_rows = st.number_input("CSV preview rows", min_value=50, max_value=10000, value=1000, step=50)

        if charts:
            st.subheader("Charts")
            grid_cols = st.columns(3)
            for idx, chart in enumerate(charts[:max_charts]):
                with grid_cols[idx % 3]:
                    st.image(chart, caption=Path(chart).name, use_column_width=True)
            if len(charts) > max_charts:
                st.caption(f"Showing first {max_charts} of {len(charts)} charts")
        else:
            st.info("No charts found.")

        if tables:
            st.subheader("CSV Tables (preview)")
            for table in tables:
                try:
                    df = load_csv_head(Path(table), nrows=int(csv_preview_rows))
                    with st.expander(f"{Path(table).name}"):
                        st.dataframe(df, use_container_width=True)
                        with open(table, "rb") as f:
                            st.download_button(
                                label="Download CSV",
                                data=f,
                                file_name=Path(table).name,
                                mime="text/csv",
                            )
                except Exception as e:
                    st.warning(f"Failed to load {table}: {e}")

        if excels:
            st.subheader("Excel Files")
            for file in excels:
                st.markdown(f"📁 `{file}`")

        if not charts and not tables and not excels:
            st.warning("No output files found in this folder.")

# -----------------------------
# MFA TAB: Run MFA
# -----------------------------
with mfa_tab:
    st.header("Run MFA")
    st.caption("Select a config and run the MFA pipeline using the runner configured in the sidebar.")

    # Default to last config if available; otherwise suggest inside model configs
    suggested_config = Path(st.session_state.get("last_config_path", structure["configs_dir"] / "mfa_config.yaml"))
    mfa_config_path = Path(st.text_input("MFA Config Path (.yaml)", str(suggested_config)))

    if st.button("Run MFA", type="primary"):
        with st.spinner("Running MFA..."):
            ok, msg = call_runner(st.session_state.get("mfa_runner", "your_module:run_mfa"), mfa_config_path)
        if ok:
            st.success("MFA run completed.")
        else:
            st.error("MFA failed")
            st.code(msg)


st.caption("Tip: You can set `SFA_MFA_BASE_DIR`, `SFA_RUNNER`, and `MFA_RUNNER` environment variables to change defaults.")