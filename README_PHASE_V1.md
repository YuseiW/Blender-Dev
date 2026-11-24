# AnimRef Phase V-1 — Viewer / Manager 同一ウィンドウ切替

基準: GitHub `YuseiW/Blender-Dev` main, commit `fd3f65ed5f7f14c2b009704ddbcbc6c4e4a9e313` (2026-11-17 08:53 UTC)

## 目的

既に動作している PySide6 の管理GUIに**閲覧ページ**を追加し、画面最上部の「閲覧（Viewer）」「登録・編集（Manager）」ボタンで同じウィンドウ内を切り替える。

- `ManagerWindow` の既存の中央ウィジェットを `takeCentralWidget()` で取り出し、`QStackedWidget` に入れる。管理パネルの再構築・Blender通信の二重化はしない。
- Viewerは **Blender Bridgeから届いたSnapshot** を使用する読み取り専用画面。メイン資料画像・指示文・登録資料一覧・カテゴリタブを表示する。
- 既存のエクスプローラー画像D&D、画像プールから登録、登録順D&D、自動スクロール、JSON上書き保存は変更しない。
- 登録・編集画面で表示尺や指示文が未保存の場合、Viewerへの移動を保留する。編集内容を保存してから切り替える。
- 新Viewerの完成までは、**Blender標準の旧ビュアーを残す**。

## インストール

1. Blender-Dev の変更をGitに保存し、**外部AnimRef ManagerのQtウィンドウを閉じる**。
2. このZIPを `Blender-Dev` のルートに展開。`apply_phase_v1.py` と `phase_v1_payload/qt_viewer_page.py` が同じ構成で置かれていることを確認する。
3. PowerShellから以下を実行する。

```powershell
python .\apply_phase_v1.py
python .\tests\test_phase_v1_contract.py
python .\tests\test_qt_save_reorder_contract.py
python .\tests\test_reference_autoscroll.py
```

4. `git diff -- scripts/addons/anim_reference_tool/ docs/` で差分を確認する。
5. Blenderの既存「資料管理ツールを開く」を押し、Qtのウィンドウを起動する。通常はBlender本体の再起動不要。

変更されたソースは `scripts/addons/anim_reference_tool/qt_manager_app.py`、新規追加は `scripts/addons/anim_reference_tool/qt_viewer_page.py`。`manager_external.py` や、カメラ重畳POCは変更しない。

`apply_phase_v1.py` は再実行しても二重適用しない。ソースの文脈が想定と違う場合は書き込まずエラー終了する。適用前のQt Managerファイルは `%TEMP%/animref_backups/phase_v1_日時/` に退避される。

## 操作と期待結果

1. 起動直後は **登録・編集（Manager）** が表示される。従来の入力・D&Dが使えることを確認する。
2. **閲覧（Viewer）** に切り替えると、カット名・Frame・メイン画像・読み取り専用の指示文・右側の資料一覧が表示される。
3. 表示中フレームの資料が一覧で強調表示され、必要な位置まで自動スクロールする。
4. Viewer右上の **原画／レイアウト／絵コンテ** を切り替えると、Blender側の `active_category` とともに画像・一覧が切り替わる。
5. **現在フレームを更新** で最新のScene/Frameを取得する。
6. **登録・編集（Manager）** に戻り、データ・選択状態・登録済み画像が維持されていることを確認する。
7. Managerで表示尺／指示文を未保存のままViewerへ移ろうとすると注意が出る。保存後に移動できる。
8. 画像登録、Explorerからの画像D&D、並べ替え自動スクロール、上書き保存、従来の独立ビュアーが正常動作することを確認する。

## V-1で未実装の範囲

- **Blenderのフレーム変更に伴うQt Viewerの自動追従はV-3**。V-1ではViewerへ移る際と「現在フレームを更新」で最新Snapshotを要求する。
- **カメラ重畳ON/OFFと不透明度スライダーはV-4**。スイッチ類は視覚的な配置のみで現在は無効。V-0では別の独立試験コードで前面重畳・不透明度が動作確認済み。
- 右の資料一覧は閲覧専用でクリックによる手動資料切替を行わない。クリック時の挙動は後続設計で決める。
- レイアウト比率、色、細部操作はV-2で調整する。

## 検証済み・未確認

**コード検査**: Python構文、現行データのフレーム範囲選択、画面切替の模擬、未保存編集ガード、パッチ冪等性、既存保存・並べ替え・自動スクロールの契約テスト PASS。

**未確認**: Windows上の実際のPySide6 UI描画、Managerの完全な操作回帰、Blender 5.2実機でのViewer切替。実際のBlender上でのテストが必要。

## Git整理

動作確認後、配布用の `apply_phase_v1.py` と `phase_v1_payload/` はGit管理に追加しなくてよい。`qt_viewer_page.py` と編集された `qt_manager_app.py`、`docs/`、継続利用する `tests/test_phase_v1_contract.py` をコミットする。
