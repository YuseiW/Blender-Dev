# AnimRef Manager — PySide6版 UI-1

**2026-11-11｜コード準備済み／Blender 5.2実機未検証**

従来の `AnimRef Manager` Workspaceと `window_new_main()` の方式は不採用。
PySide6の**独立した資料管理GUI**を外部Pythonプロセスで開く。
既存の画像同期・独立ビュアーはBlender内に残す。

## 1. 必要環境

- Windows, Blender 5.2.x
- 外部Python 3.10以上（PySide6対応版、3.14でも可）
- PySide6

WindowsのPowerShellでインストール（BlenderのPythonコンソールでは実行しない）：

```powershell
py -3 -m pip install PySide6
py -3 -c "from PySide6 import QtWidgets; print('PySide6 OK')"
```

`py` コマンドがない場合は次を試す。

```powershell
python -m pip install PySide6
python -c "from PySide6 import QtWidgets; print('PySide6 OK')"
```

Blenderが利用するPythonを明示したい場合は、起動**前に**Windows環境変数 `ANIMREF_PYTHON` に外部 `python.exe` の**フルパス**を設定する（Blender内蔵Pythonは使用しない）。

## 2. コードの適用

1. ZIPを `Blender-Dev` フォルダ直下へ展開。
2. `apply_animref_qt_ui1.py` と `animref_qt_ui1_payload/` が直下にあることを確認。
3. PowerShellで次を実行。

```powershell
python .\apply_animref_qt_ui1.py
python -m compileall -q .\scripts\addons\anim_reference_tool

git diff -- docs/ scripts/addons/anim_reference_tool
```

4. Blenderの作業中 `.blend` を保存、Blenderを完全終了して再起動。
5. LayoutのNパネル → `AnimRef` → **資料管理ツールを開く**。
6. Blender 3Dビューではなく、単独の `AnimRef Manager — 資料登録` ウィンドウが現れる。

`AnimRef Manager` という旧ワークスペースタブが以前のパッチによって作られていた場合は、新GUIの正常動作を確認してから手動で削除する。古い `.blend` を自動編集しない。

## 3. 操作

- 左上の **絵コンテ／レイアウト／原画** で種別を変更。
- `Cut` を選択。必要なら「＋ カット」。
- 右の **画像を追加…** からファイルを読み込む。
- 右サムネイルを選択して **← 選択画像を登録**、または左の一覧へドラッグ。
- 左の登録順から項目を選択し、尺・指示文を編集後「表示尺・指示文を保存」。
- 左の「上へ」「下へ」「削除」は既存Reference Manager経由。
- 上部の **JSON保存／JSON読込** は既存の `project_io` を呼び出す。
- 右のサムネイル下の色帯は登録カテゴリ。緑＝絵コンテ、青＝レイアウト、赤＝原画。複数カテゴリに使用した画像は複数の帯。

### 注意点

- GUIからの変更はまずBlenderの**現在のScene**へ反映される。保存したい場合はBlenderの `.blend` またはGUIのJSON保存を行う。
- UIはBlenderの最初に開いたウィンドウに接続する。BlenderでSceneを切り替えたら上部「更新」でScene情報を再取得する。
- `.blend` ファイルを読み替えたら管理GUIを閉じ、Blenderから再度開く。
- QtアプリはBlenderの `bpy` を直接importしない。Blender本体で `bpy.app.timers` を使い命令を処理する。
- GUIを閉じると通信セッションは終了する。Qtの複数起動は防止する。
- 画像プールのサムネイルが読めない形式はプレースホルダーを表示する。Blender側の画像登録とは独立。

## 4. テスト

1. 旧Blenderワークスペースや新規Blenderウィンドウではない、PySide6専用GUIが開く。
2. 左＝登録、右＝画像プールの配置になっている。
3. 画像を追加し、2列サムネイルが表示される。
4. 左へD&Dまたは追加ボタンで、Blender SceneにReferenceItemを追加できる。
5. 尺・指示文を保存し、BlenderのNパネルおよび専用ビュアーへ反映される。
6. JSON保存／読込でBlender側の画像／カット／指示文が復元される。
7. GUIを閉じてもBlenderの3Dビュー、既存独立ビュアー、Timeline同期が動く。
8. 管理GUIを開いた状態で再度ボタンを押しても増殖しない。

## 5. エラー時

- ボタンで「PySide6が見つかりません」→PowerShellでPySide6のpipインストールと起動Pythonの確認。
- GUIは現れるが「Blenderから応答がありません」→Blenderが閉じられたり `.blend` を再読み込みした可能性。GUIを閉じて起動し直す。
- ボタンを押してもGUIが現れない→Blenderのシステムコンソールでエラーを確認。外部Pythonで以下のレイアウト検証を試す。

```powershell
py -3 .\scripts\addons\anim_reference_tool\qt_manager_app.py --demo
```

`--demo` はGUIの外見だけを表示する。Blenderとは接続しない。

## 6. 設計判断の変更

D-001で「Blenderアドオン単体」としていた設計は、**管理GUIに限りD-005で明示的に変更**した。外部Qt側のPythonは新規依存。Blenderの標準独立リファレンスビュアーは残す。
