# AnimRef Phase V-5.3 — 旧UIソース整理・リリース候補

更新：2026-11-18

## 現時点で確認できている事実

- Phase V-4：実機8項目 PASS（ユーザー報告）
- Phase V-5：重点実機8項目 PASS（ユーザー報告）
- Phase V-5.2：旧UI退役実機7項目 PASS（ユーザー報告）
- Phase V-5詳細16項目：**個別の結果はまだ報告されていない**。すべてPASSしたとは記録しない。
- GitHub `main` は少なくとも確認時点ではV-5.2までの最新版とは異なる。**ローカルを正本として扱う**。

## 変更範囲

`apply_phase_v5_3.py` は登録解除済みの以下の旧Pythonソースだけを削除する（存在する場合）。

- `scripts/addons/anim_reference_tool/ui/viewer_panel.py`
- `scripts/addons/anim_reference_tool/ui/reference_editor.py`
- `scripts/addons/anim_reference_tool/ui/manager_panels.py`
- `scripts/addons/anim_reference_tool/operators/viewer.py`
- `scripts/addons/anim_reference_tool/operators/manager_workspace.py`

上記モジュールの**importがほかに残っていれば削除を拒否**する。

`docs/CURRENT_SPEC.md`、`docs/DEVELOPMENT_LOG.md`、`docs/DECISIONS.md` に最新状況を追記し、`.gitignore` にPython生成物とローカル環境の除外パターンを追加する。既存の文章は削除・上書きしない。

**変更しない**：`qt_manager_app.py`、`qt_viewer_page.py`、`manager_ipc.py`、`operators/manager_external.py`、`camera_overlay_manager.py`、`timeline_manager.py`、`image_manager.py`、`viewer_manager.py`、BlenderのProject、保存JSON、`.blend`。

`viewer_manager.py`などの古い互換ロジックは`image_manager.py`に参照が残っているため、今回削除しない。物理削除を進めるには別途リファクタリングと追加回帰テストが必要。

## 事前準備

1. 動作確認済みV-5.2のローカルソースをGitにコミットする。
2. Blender・Qt AnimRefを終了する。`.blend`およびプロジェクトJSONを保存・バックアップする。
3. ZIP内のファイルを `BlenderDev` の**ルート**へ展開する。
4. Pythonが実行できるPowerShellを開く。

## 適用

最初は読み取り専用で変更箇所を表示する。

```powershell
python .\apply_phase_v5_3.py --check
```

削除予定ファイルと更新予定ドキュメントが意図どおりであることを確かめてから実行する。

```powershell
python .\apply_phase_v5_3.py --apply
python .\tests\test_phase_v5_3_contract.py
python .\tests\test_phase_v5_3_installer.py
.\run_v5_3_tests.ps1
```

適用時には `%TEMP%\animref_backups\phase_v5_3_...` に**削除対象と更新前ドキュメントをバックアップ**する。部分的なエラーが発生したら変更したファイルを元に戻す。

### 旧PythonキャッシュをGitで追跡している場合

`.gitignore` は将来の追加を防ぐだけで、**すでにGit管理下の.pycは解除しない**。

```powershell
git ls-files | Select-String '__pycache__|\.pyc$'
```

もし表示されたら、対象のパスだけ `git rm --cached` で追跡解除し、ローカルPythonキャッシュを必要に応じて削除する。特に作業中の他ファイルは勝手に削除しない。

## 実機確認

Blenderを再起動し、Nパネルの「AnimRefを開く」からViewerを起動して、以下を再確認する。

- Viewer ⇄ Managerの画面切替、カットとカテゴリの切替。
- Timeline同期ON/OFF、画像と指示文、強調表示。
- カメラ重畳ON/OFFと不透明度（0/50/100%）。
- ManagerのD&D・資料尺・指示文編集・JSON保存。
- 通常Image Editorの画像がTimeline操作で書き換えられないこと。
- Blender/Qtの再起動。

詳細な16項目は `PHASE_V5_3_FINAL_CHECKLIST.md` を参照。ユーザーがすでに確認したV-5.2の7項目は再試験済みの記録として扱うが、**新たなV-5.3のコード整理後のスモークテストは別途必要**。

## Gitへの反映

検証が通った後に差分を確認する。

```powershell
git status --short
git diff --stat
git diff -- docs/CURRENT_SPEC.md docs/DEVELOPMENT_LOG.md docs/DECISIONS.md
python -m compileall -q .\scripts\addons\anim_reference_tool
git add -A
git diff --cached --stat
git commit -m "Finalize AnimRef Qt viewer and retire legacy UI"
git push origin main
```

**注意**：`git add -A` はローカルのすべての変更を対象とする。不要なテスト素材・パッチZIP・バックアップがステージされていないか `git diff --cached --stat` で必ず確認する。必要に応じてファイルを指定して `git add` する。

このアシスタント側からGitHubへは今回コミット／プッシュしていない。ユーザーのローカル版を最新として反映してほしい。

## ロールバック

バックアップ場所は適用後に表示される。Blender・Qtを終了し、バックアップした旧ファイルを同じ相対パスへ戻して再起動する。または事前のGitコミットから元に戻す。ユーザーデータには手を加えない。

## 位置づけ

V-5.3は**旧UIの物理削除とリポジトリ整理**であり、新しい表示機能は追加しない。V-5詳細16項目、最終ソースのGitHubプッシュおよび文書更新を確認した時点でリリース完了と判断する。
