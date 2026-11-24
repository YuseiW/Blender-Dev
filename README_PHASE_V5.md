# AnimRef Phase V-5 — 統合試験とScene/Camera安定化（第一段階）

Phase V-4の8項目が実機PASSした状態から適用する。**本パッチは V-5の第一段階**。16項目の総合試験が完了するまではV-5を完了扱いにしない。

## 対象となる問題

BlenderのSceneを複製すると、カスタムプロパティに保存した重畳所有トークンまでコピーされる。一方、Camera背景画像はカメラ**データブロック**に属する。V-4では複製Sceneが同じ所有者と判定され、一方の重畳更新が他方を消してしまう可能性があった。

### V-5追加処理

- Scene複製時に重畳所有トークンが重複していたら、元のSceneを保護し、複製先へ新しいトークンを割り当てる。
- **同じCameraデータブロックを共有するScene**では、その時点で操作しているSceneのAnimRef重畳だけを残す。元々あったユーザーのカメラ背景画像は対象外。
- Scene削除後に残るAnimRef-owned背景画像を、アドオン解除時に安全に清掃する。
- 背景表示フラグは、そのカメラからAnimRefの重畳が**すべて消えたときだけ**元の状態に戻す。
- Blenderのデータ構造、プロジェクトJSON、Timeline同期、Qt Viewer/Manager、Nパネルは変更しない。

**制限**：1つのCameraデータブロックに同時に別々の重畳を表示することはできない。複数Sceneの同時独立表示が必要なら、カメラオブジェクトだけでなくCameraの**データもシングルユーザー化**すること。

## 導入

1. `.blend`とJSONを保存し、正常なV-4を `git commit` しておく。BlenderとQtを終了する。
2. ZIPを`Blender-Dev`のルートへ展開する。
3. PowerShellで以下を実行する。

```powershell
python .\apply_phase_v5.py
python .\tests\test_phase_v5_contract.py
```

4. [PHASE_V5_TEST_MATRIX.md](PHASE_V5_TEST_MATRIX.md)にあるV-1〜V-4の回帰テストを実行する。
5. Blenderを再起動し、テスト用に複製した `.blend` でシーン切替などを検証する。
6. 可能なら `tools/phase_v5_diagnostics.py` をScriptingのText EditorでRun Scriptし、Scene/Camera共有や欠損ファイルを確認する。

### パッチの安全性

対象は `scripts/addons/anim_reference_tool/camera_overlay_manager.py` のみ。導入スクリプトはV-4の既知のSHA256と一致する場合だけ置換し、`%TEMP%\animref_backups\phase_v5_日時\`にバックアップする。再実行は無変更で終了する。既に独自変更があれば中止し、手作業で差分を確認する。

V-4実機の正常動作を損なわないよう、Qt側・Manager側のコードや既存テストは書き換えない。必要なテスト・診断スクリプトを追加するだけだ。

### データ保全の注意

**試験は必ず `.blend` のコピーで行う**。Camera背景画像はCameraデータブロックに保存されるため、共有Cameraの元データへ影響する。バックアップなしで複数Sceneの本番プロジェクトを上書きしない。

### テスト状況（配布時）

- V-5 模擬テスト：Scene複製・異なるCamera、共有Camera、解除時復元、Scene削除後の孤立レイヤー清掃 — PASS
- V-1 / V-2 / V-3 / V-3.1 / V-3.2 / V-4の既存契約テスト — PASS（ローカル再構成テスト環境）
- Blender 5.2 + PySide6 **V-5変更後の実機試験 — 未実施**

### 完了判定

試験表の各項目をPASS / FAIL / 未実施で記録し、FAILを修正・再試験した後、既存の`docs/DEVELOPMENT_LOG.md`と`docs/CURRENT_SPEC.md`を**実際の結果に沿って**更新してからV-5完了とする。旧Blender Image Editorビュアーはまだ削除しない。互換性確認後に扱いを決定する。
