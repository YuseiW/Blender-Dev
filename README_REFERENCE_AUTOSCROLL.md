# AnimRef Manager — 登録順リストのD&D自動スクロール

対象: 2026-11-17時点の **PySide6版 UI-1 + Explorer D&D + Save/Reorder** を導入済みの Blender-Dev。

## 変更範囲

- 変更するファイルは `scripts/addons/anim_reference_tool/qt_manager_app.py` のみ。
- Blender側の `manager_external.py`、データモデル、JSON保存形式、独立リファレンスビュアーは変更しない。
- 既存の画像プールからの登録D&D、エクスプローラーからの取り込みD&Dは維持。

## 導入

1. このZIPを `Blender-Dev/` に展開する。
2. `Blender-Dev` 直下のPowerShellで以下を実行する。

```powershell
python .\apply_reference_autoscroll.py
python .\tests\test_reference_autoscroll.py
```

3. `git diff -- scripts/addons/anim_reference_tool/qt_manager_app.py` で差分を見る。
4. **AnimRef ManagerのQtウィンドウを完全に閉じてから開き直す。** Blender本体はそのままでよい（新しいQtを再起動できない場合はBlenderも再起動）。

`apply_reference_autoscroll.py` は同じものを再適用しても二重に追記しない。適用前の `.py` は `%TEMP%\animref_backups\reference_autoscroll_...\qt_manager_app.py` へコピーする。既存コードが想定と違う場合はエラーで停止し、ファイルを変更しない。

## 使い方

左側の登録済み資料がリストの高さを超える状態で、項目をドラッグして、カーソルを登録リストの**上端**に近づけると上へ、**下端**に近づけると下へ自動スクロールする。

- 動き始める範囲はリストの端から最大64ピクセル（リストが小さければそれに合わせ縮小）。
- 端に近いほど速く、端から離れるほど遅くなる。
- カーソルを端に置いたままでも、40ミリ秒未満の周期で継続する（35ms）。
- 中央に戻す／リスト外へ出す／ドロップする／Escで中止すると停止する。
- 先頭・末尾ではスクロールが止まる。
- ドロップ位置は既存の `_insertion_index_at()` が決め、Blender側 `reorder_reference` により実際の資料順を変更する。スクロール自体は資料順を変更しない。

## 動作確認

1. 登録資料を10枚以上作り、左側の一覧に縦スクロールバーを表示する。
2. 下方の資料を掴んで上端までドラッグし、静止しても上へスクロールするか。
3. 上方の資料を掴んで下端までドラッグし、静止しても下へスクロールするか。
4. 中央へ動かしたら停止するか。
5. スクロール先でドロップすると資料が指定位置へ移動し、フレーム範囲が再計算されるか。
6. ドラッグをEscで中止したあと勝手にスクロールしないか。
7. 画像プールからの資料登録、Explorerから画像プールへの取り込み、JSON上書き保存は従来どおりか。

## 検証済み範囲

- Python構文検査、適用スクリプトの再実行、端検出の単体テスト、スクロールバーの模擬動作テスト、従来の保存・D&D並べ替え契約テスト: PASS。
- 実際のWindows/PySide6 GUIドラッグ操作: **未確認**。Qt起動後に実機確認が必要。
