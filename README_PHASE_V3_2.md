# AnimRef — Phase V-3.2 同期制御修正 / Nパネル起動専用化

対象：**Phase V-3.1適用済み**の `Blender-Dev` ローカル作業ツリー。

## なぜ修正するか

V-3.1で、Qt Viewerの「自動同期」スイッチを操作した際、QtがバックグラウンドでBlenderの状態を取得している最中だと、スイッチ操作を送信せずに元へ戻す経路が残っていた。加えて、3Dビューの旧Nパネルにも同期スイッチがあり、操作の所在がわかりにくかった。

今回の修正では **Blenderの `Scene.animref_project.auto_sync` を唯一の設定値**とし、ユーザーが直接操作する入口をQt Viewerへ集約する。Qtの状態取得と操作送信が競合した際は、最後のユーザー操作を保留し、通信が空き次第 `set_auto_sync` を送信する。Blenderからの応答が確定するまではQtのチェック表示を不用意に戻さない。

**注意：** 実機での症状の原因がこの競合だけだったかは未確定。今回の改修はコード上で確認できた操作消失の経路を解消するもの。

## UI変更

- Blender **3DビューのNパネル > AnimRef** は **「AnimRefを開く」** ボタンのみ。
- 旧3Dビュー用「Reference Editor」は登録を解除。元のPythonファイルは削除せず保持。
- 既存のBlender **Image Editor専用ビュアー**と、その情報NパネルはV-5の互換性確認まで維持。
- Viewerの自動同期、カテゴリ、カット切替、およびManagerの資料登録・保存などは維持。
- 旧Nパネルの変更によって、Blender側の `auto_sync` プロパティ、Timeline Handler、既存Manager通信は削除しない。

## 導入手順

1. 作業内容を保存し、Blenderと外部Qtアプリを完全終了する。
2. `git status` で作業ツリーを確認し、可能なら現在の動作状態をGitでコミットする。
3. ZIPの内容を **`Blender-Dev` リポジトリのルート** に展開する（`apply_phase_v3_2.py` がルート直下に来るように）。
4. PowerShellで、リポジトリのルートから実行する。

```powershell
python .\apply_phase_v3_2.py
python .\tests\test_phase_v3_2_contract.py
python .\tests\test_phase_v3_1_contract.py
python .\tests\test_phase_v3_contract.py
python .\tests\test_phase_v2_contract.py
python .\tests\test_phase_v1_contract.py
```

5. **Blender自体を再起動**して、Nパネルの「AnimRefを開く」からQtアプリを起動する。
6. QtのViewerに切り替え、動作を確認する。

適用スクリプトは内容と実装バージョンを確認し、適用前に `%TEMP%\animref_backups\phase_v3_2_日時` に元ファイルをバックアップする。重複実行では追加の変更を行わない。

## 実機で確認する内容

1. 3DビューのNパネル「AnimRef」には「AnimRefを開く」ボタンのみ表示される。
2. Qt Viewerで自動同期ONにすると、BlenderのTimelineを移動した際に画像・指示文・資料強調表示が追従する。
3. Qt Viewerで自動同期OFFにすると表示を固定できる。OFF→ONで現在フレームへ戻る。
4. スイッチを短い間隔でON/OFFしても、直後の設定が失われない。
5. Blender Python Consoleで次を実行し、Qtのスイッチ状態とBlenderが保持する実値が一致する。

```python
bpy.context.scene.animref_project.auto_sync
```

6. Viewerのカット選択、Managerの画像追加・D&D並べ替え・JSON保存が引き続き利用できる。
7. **旧独立ビュアーもまだ残す**。必要ならBlender Consoleで `bpy.ops.animref.open_viewer()` を使用できる（有効な3Dビューのコンテキストが必要）。

## 変更箇所

| ファイル | 変更 |
|---|---|
| `qt_manager_app.py` | 同期切替要求の保留・再送、ACK確認、失敗時の復旧 |
| `qt_viewer_page.py` | 未確定のスイッチ状態を古い通知で上書きしない |
| `ui/main_panel.py` | 3DビューNパネルを起動ボタンだけにする |
| `ui/__init__.py` | 古い3D用Reference Editorの登録を止める |
| `tests/test_phase_v3_contract.py` | 旧実装専用だった静的検査を新旧両方で通る判定に修正 |
| `docs/` | 現行仕様と開発ログに変更内容を追記（ファイルが存在する場合のみ） |

**変更なし：** `properties.py`、`timeline_manager.py`、`project_io.py`、登録データとJSON形式、旧Image Editorビュアー。

## 実施済みの確認と制約

- Python構文検査とV-3.2の模擬試験：PASS
- V-1、V-2、V-3、V-3.1の既存契約試験：PASS
- 同一パッチの再適用：内容を変更せず終了
- **Blender 5.2 / Windows + PySide6 実機：未実施**。ユーザー側の動作確認が必要。

V-3.2が成功したら、次は **Phase V-4：カメラ重畳のViewer本体統合**。
