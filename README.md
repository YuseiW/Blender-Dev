# AnimRef — Blender Animation Reference Tool

BlenderのTimelineと絵コンテ・レイアウト・原画を連携する制作支援アドオン。

## 動作環境・起動

開発環境はWindows、Blender、外部PythonとPySide6。既存のアドオン導入方法を維持する。外部Pythonに `python -m pip install PySide6` で依存を導入し、必要なら環境変数 `ANIMREF_PYTHON` で実行ファイルを指定する。Blenderでアドオンを有効化し、3D ViewのNパネルから「AnimRefを開く」。

## 構成

`scripts/addons/anim_reference_tool/`: `core/`, `storage/`, `managers/`, `ipc/`, `qt/`, `operators/`, `ui/`。

## テスト

`python tests/run_regression.py` は非GUI回帰試験。`tests/integration_smoke.py` はBlender内で実行する。`tests/pending/` は旧UI撤去後に実行する受入試験であり、通常回帰試験から除外する。

仕様と開発履歴は `docs/` を参照。
