"""Run ONCE or repeatedly from the Blender-Dev repository root:

    python apply_ui1.py

This script only writes the two new modules and makes small idempotent
changes in the existing registration/UI files. It does not run Blender.
"""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / "scripts" / "addons" / "anim_reference_tool"
PAYLOAD = ROOT / "ui1_payload" / "scripts" / "addons" / "anim_reference_tool"


def insert_once(path, anchor, inserted, already):
    source = path.read_text(encoding="utf-8")
    if already in source:
        return False
    count = source.count(anchor)
    if count != 1:
        raise RuntimeError(
            f"Cannot find a unique insertion anchor in {path} (found {count})"
        )
    path.write_text(source.replace(anchor, inserted + anchor, 1), encoding="utf-8")
    return True


def main():
    required = [
        ADDON / "ui" / "__init__.py",
        ADDON / "operators" / "__init__.py",
        ADDON / "ui" / "main_panel.py",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Expected Blender-Dev repository at {ROOT}: {path}")

    for rel in ["ui/manager_panels.py", "operators/manager_workspace.py"]:
        source = PAYLOAD / rel
        dest = ADDON / rel
        if not source.is_file():
            raise FileNotFoundError(source)
        if dest.exists() and dest.read_bytes() != source.read_bytes():
            raise RuntimeError(
                f"File already exists with different content: {dest}. Stop to avoid overwriting."
            )
        if not dest.exists():
            shutil.copy2(source, dest)
            print("Created:", dest.relative_to(ROOT))

    operators_init = ADDON / "operators" / "__init__.py"
    ui_init = ADDON / "ui" / "__init__.py"
    main_panel = ADDON / "ui" / "main_panel.py"

    insert_once(
        operators_init,
        "from . import viewer\n",
        "from . import manager_workspace\n",
        "from . import manager_workspace",
    )
    insert_once(
        operators_init,
        "    viewer,\n",
        "    manager_workspace,\n",
        "    manager_workspace,",
    )
    insert_once(
        ui_init,
        "from . import reference_editor\n",
        "from . import manager_panels\n",
        "from . import manager_panels",
    )
    insert_once(
        ui_init,
        "    reference_editor,\n",
        "    manager_panels,\n",
        "    manager_panels,",
    )
    insert_once(
        main_panel,
        "        # Reference Viewer\n",
        "        layout.operator(\n"
        "            \"animref.open_manager_workspace\",\n"
        "            text=\"AnimRef Managerを開く\",\n"
        "        )\n\n"
        "        # --------------------------------\n",
        '"animref.open_manager_workspace",',
    )
    setup_src = ROOT / "ui1_payload" / "docs" / "UI1_SETUP.md"
    setup_dest = ROOT / "docs" / "UI1_SETUP.md"
    if setup_src.is_file() and not setup_dest.exists():
        shutil.copy2(setup_src, setup_dest)
        print("Created:", setup_dest.relative_to(ROOT))

    spec_path = ROOT / "docs" / "CURRENT_SPEC.md"
    if spec_path.is_file():
        spec = spec_path.read_text(encoding="utf-8")
        before = spec
        spec = spec.replace(
            "開発段階: Phase 1完了 / Phase 2開始前",
            "開発段階: Phase 2-A完了（回帰12/12 PASS） / UI-1実装・検証中",
        )
        spec = spec.replace(
            "- 現在はすべてのImage Editorが同期対象。\n- ビュアー専用の表示先管理は未実装。",
            "- 専用ビュアーが開いている場合はそのImage Editorだけを同期する。\n"
            "- ビュアーがない場合は互換性のため全Image Editorを同期する。",
        )
        if "### UI-1 画面構成" not in spec:
            section = (
                "### UI-1 画面構成\n\n"
                "- 左: 資料登録領域 / 右: 画像プール（ユーザー確定）。\n"
                "- Blender標準のAnimRef Managerワークスペースを利用。\n"
                "- UI-1は登録・画像プールのリスト表示まで。\n"
                "- サムネイル・属性色・D&Dは後続UI工程。\n"
                "- Blender実機でのUI-1動作確認は未実施。\n\n"
            )
            anchor = "## 6. 現在の制約"
            if anchor not in spec:
                raise RuntimeError("Missing UI section insertion anchor in CURRENT_SPEC.md")
            spec = spec.replace(anchor, section + anchor, 1)
        if spec != before:
            spec_path.write_text(spec, encoding="utf-8")
            print("Updated:", spec_path.relative_to(ROOT))

    decisions_path = ROOT / "docs" / "DECISIONS.md"
    if decisions_path.is_file():
        decisions = decisions_path.read_text(encoding="utf-8")
        changed = decisions.replace(
            "状態: 採用方針・未実装", "状態: 採用・Phase 2-A動作確認済み", 1
        )
        if changed != decisions:
            decisions_path.write_text(changed, encoding="utf-8")
            print("Updated:", decisions_path.relative_to(ROOT))

    log = ROOT / "docs" / "DEVELOPMENT_LOG.md"
    log_entry = ROOT / "ui1_payload" / "docs" / "UI1_LOG_ENTRY.md"
    if log.is_file() and log_entry.is_file():
        original = log.read_text(encoding="utf-8")
        if "UI-1 / 管理ワークスペースと左右2領域の実装" not in original:
            log.write_text(
                log_entry.read_text(encoding="utf-8") + "\n" + original,
                encoding="utf-8",
            )
            print("Updated:", log.relative_to(ROOT))

    print("UI-1 code installation complete. Verify with git diff and restart Blender.")


if __name__ == "__main__":
    main()
