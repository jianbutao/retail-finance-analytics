import streamlit as st

from .config import project_root, resolve_path
from .evidence import TABLE_SOURCES, load_evidence_inputs


@st.cache_data(show_spinner="加载已验证的分析成果……", max_entries=2)
def _read_tables(version_key):
    tables, _, _ = load_evidence_inputs()
    return tables


def page_data():
    """各页面共用的归档读取入口；不清洗、不训练、不写文件。"""
    try:
        config_text = (
            project_root() / "config/project.json"
        ).read_text(encoding="utf-8")

        paths = [
            resolve_path(key) / filename
            for key, filename in TABLE_SOURCES.values()
        ]
        paths.append(resolve_path("risk_report") / "manifest.json")

        version_key = (
            config_text,
            tuple(
                (str(path), path.stat().st_mtime_ns, path.stat().st_size)
                for path in paths
            ),
        )
        return _read_tables(version_key)

    except (OSError, ValueError, KeyError) as error:
        st.error(f"分析成果加载失败：{error}")
        st.stop()