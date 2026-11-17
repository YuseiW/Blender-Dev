"""Apply UI-1 popup correction to an existing UI-1 installation.

Put this file in the Blender-Dev repository root and run:
    python fix_ui1_window.py

No Blender runtime required. Makes .ui1_popup_backup copies before editing.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / "scripts" / "addons" / "anim_reference_tool"
OP = ADDON / "operators" / "manager_workspace.py"
PANEL = ADDON / "ui" / "manager_panels.py"
MAIN = ADDON / "ui" / "main_panel.py"
BUNDLE = ROOT / "ui1_popup_fix_bundle"
BACKUP = ROOT / "ui1_popup_backup"


def backup(path):
    BACKUP.mkdir(exist_ok=True)
    target = BACKUP / (path.parent.name + "_" + path.name)
    if not target.exists():
        shutil.copy2(path, target)


def main():
    for path in (OP, PANEL, MAIN):
        if not path.is_file():
            raise FileNotFoundError(f"Previous UI-1 installation not found: {path}")
    replacement = (BUNDLE / "manager_workspace.py").read_text(encoding="utf-8")
    old_operator = OP.read_text(encoding="utf-8")
    if old_operator != replacement:
        if (
            "ANIMREF_OT_OpenManagerWorkspace" not in old_operator
            or "animref.open_manager_workspace" not in old_operator
        ):
            raise RuntimeError("Unexpected operator file. Stop, inspect manually: " + str(OP))
        backup(OP)
        OP.write_text(replacement, encoding="utf-8")
        print("Updated", OP.relative_to(ROOT))

    panel = PANEL.read_text(encoding="utf-8")
    old_helper = '''MANAGER_WORKSPACE_NAME = "AnimRef Manager"\n\n\ndef _is_manager_workspace(context):\n    window = getattr(context, "window", None)\n    return bool(\n        window is not None\n        and window.workspace is not None\n        and window.workspace.name == MANAGER_WORKSPACE_NAME\n        and getattr(context, "scene", None) is not None\n        and hasattr(context.scene, "animref_project")\n    )\n'''
    new_helper = '''MANAGER_SCREEN_KEY = "animref_manager_window"\n\n\ndef _is_manager_workspace(context):\n    """Show panels only in the dedicated separate manager window."""\n    window = getattr(context, "window", None)\n    screen = window.screen if window is not None else None\n    return bool(\n        screen is not None\n        and screen.get(MANAGER_SCREEN_KEY, False)\n        and getattr(context, "scene", None) is not None\n        and hasattr(context.scene, "animref_project")\n    )\n'''
    if old_helper in panel:
        backup(PANEL)
        PANEL.write_text(panel.replace(old_helper, new_helper, 1), encoding="utf-8")
        print("Updated", PANEL.relative_to(ROOT))
    elif new_helper not in panel:
        raise RuntimeError("Unexpected manager panel helper. Stop: " + str(PANEL))

    old_label = 'text="AnimRef Managerを開く",'
    new_label = 'text="AnimRef Manager（別ウィンドウ）",'
    main_text = MAIN.read_text(encoding="utf-8")
    if old_label in main_text:
        backup(MAIN)
        MAIN.write_text(main_text.replace(old_label, new_label, 1), encoding="utf-8")
        print("Updated", MAIN.relative_to(ROOT))
    elif new_label not in main_text:
        raise RuntimeError("Manager button label not found in main_panel.py")

    log_path = ROOT / "docs" / "DEVELOPMENT_LOG.md"
    if log_path.exists():
        log = log_path.read_text(encoding="utf-8")
        marker = "### UI-1 / 独立ウィンドウへの設計修正"
        if marker not in log:
            entry = '''## 2026-11-11\n### UI-1 / 独立ウィンドウへの設計修正\n\n状態: 修正コード準備・Blender実機での再検証待ち\n\n- 発見: 前回のUI-1はWorkspaceを追加する方式だった\n- ユーザー要件: メインBlender画面とは独立した別ウィンドウ\n- 修正: bpy.ops.wm.window_new_main()を使用\n- 画面: 左＝資料登録 / 右＝画像プール\n- 既存ワークスペースの自動削除は行わない\n- 既存ビュアー、JSON、データモデルは変更しない\n- 実機テスト: 未実施\n\n---\n\n'''
            log_path.write_text(entry + log, encoding="utf-8")
            print("Updated", log_path.relative_to(ROOT))

    spec_path = ROOT / "docs" / "CURRENT_SPEC.md"
    if spec_path.exists():
        spec = spec_path.read_text(encoding="utf-8")
        spec = spec.replace(
            "- Blender標準のAnimRef Managerワークスペースを利用。",
            "- Blender標準の別ウィンドウを利用し、メイン画面を変更しない。",
        )
        if "### UI-1 画面構成" in spec:
            a = spec.index("### UI-1 画面構成")
            b = spec.find("## 6.", a)
            if b >= 0:
                sec = spec[a:b]
                sec = sec.replace("- Blender実機でのUI-1動作確認は未実施。", "- UI-1別ウィンドウ方式は実機再テスト待ち。")
                spec = spec[:a] + sec + spec[b:]
        spec_path.write_text(spec, encoding="utf-8")
        print("Updated", spec_path.relative_to(ROOT))

    print("Patch applied. Save .blend and RESTART Blender. Test from Layout workspace.")
    print("Old 'AnimRef Manager' workspace tab is not deleted automatically.")


if __name__ == "__main__":
    main()
