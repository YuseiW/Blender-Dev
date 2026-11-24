# AnimRef — Phase V-2 Viewer 表示・操作性改善

対象：Phase V-1（Viewer/Manager画面切替）を導入済みの `Blender-Dev` リポジトリ。

## 今回の実装内容

- Viewerのメイン画像を `QGraphicsView` で表示し、**マウスホイールで拡大・縮小**。
- **画像上で左ボタンを押したままドラッグ**すると表示領域を移動（パン）。
- **「全体表示」**で画像を縦横比を維持して画面内に収める。
- **「100%」**で画像をソース画像のピクセル等倍スケールで表示する。
- 画像が切り替わった場合は全体表示に戻る。同じ画像の情報更新ではズーム位置を保持。
- 右側登録資料一覧は表示中のアイテムを **カテゴリ色** で強調。現在の資料が切り替わったら該当行へ自動スクロール。
- 同じカット・同じ登録内容でのスナップショット更新は一覧を再生成しないため、ユーザーが手動でスクロールした位置を保持する。

今回のViewerは **閲覧専用**。資料のインポート・並べ替え・フレーム長や指示文の修正・JSON保存は従来のManagerが担当。

**まだ追加しないもの：** Timelineの継続自動追従（V-3）、カメラ重畳の本体接続・スイッチ・不透明度（V-4）、資料クリックによる表示切替やTimelineジャンプ（仕様未確定）。今回の同期トグルと重畳トグルはまだ無効。

## 適用方法

1. まず `.blend` や現在のJSONを保存し、QtのAnimRefウィンドウを閉じる。
2. ZIPを `Blender-Dev` の直下に展開する。`apply_phase_v2.py`、`phase_v2_payload/`、`tests/` ができる。
3. PowerShell（プロジェクト直下）で実行する。

```powershell
python .\apply_phase_v2.py
python .\tests\test_phase_v2_contract.py
```

4. （任意）以前の `apply_phase_v1.py` と `test_phase_v1_contract.py` が残っていれば、`python .\tests\test_phase_v1_contract.py` も実行する。
5. `git diff -- scripts/addons/anim_reference_tool/qt_viewer_page.py docs/` で差分を確認する。
6. Blenderの `AnimRef` から **資料管理ツールを開く**。上部の **閲覧（Viewer）** へ切り替える。

**Blenderを再起動する必要は通常ない。** Qtウィンドウを完全に閉じて開き直してくれ。変化しない場合はBlenderも再起動して確認する。

`apply_phase_v2.py` はすでにV-2が入っていれば重複適用しない。適用前の`qt_viewer_page.py`をWindowsの `%TEMP%\animref_backups\phase_v2_...` にコピーする。想定外の旧ファイルや、ローカルで編集した別のV-2がある場合は上書きを拒否する。

## 動作テスト（実機）

1. ViewerとManagerを往復でき、Managerのインポート・D&D・上書き保存・自動スクロールに問題がない。
2. Viewerのメイン画像上でホイール上→拡大、ホイール下→縮小。
3. 拡大中に画像をドラッグして見たい部分へ移動できる。
4. **全体表示**で画像の全体が枠内に収まり、縦横比が変わらない。
5. **100%**を押すと等倍へ戻る。
6. 原画・レイアウト・絵コンテの各タブで一覧とメイン画像が適切に切り替わる。
7. Blenderのフレームを変更後、**現在フレームを更新**すると対応資料が強調され、一覧が該当行へスクロールする。
8. 同じ資料を再取得してもズーム状態と一覧の手動スクロール位置が保持される。
9. 未登録フレーム・ファイル欠損では空表示かエラーメッセージになり、Qtが落ちない。

**ロジック検査済み**：構文、画像選択の境界、ズーム値の上限下限、一覧更新判定、V-1との互換性。Qt/Blender実機は未確認。

## 変更ファイル

- `scripts/addons/anim_reference_tool/qt_viewer_page.py`（置換）
- `docs/CURRENT_SPEC.md`、`docs/DEVELOPMENT_LOG.md`（追記）
- `tests/test_phase_v2_contract.py`（追加）

`qt_manager_app.py`、`manager_external.py`、`manager_ipc.py`、その他Blender側の同期・登録・保存コードは変更しない。
