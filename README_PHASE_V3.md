# AnimRef — Phase V-3：Blender Timeline 自動同期

対象：**Phase V-2 の6項目を実機で確認済みの Blender-Dev**。
このパッチは既存の PySide6 Viewer／Manager に Blender Timeline の継続同期を追加する。

## 追加する動作

- Blender でフレームを変更すると、Qt Viewer のメイン画像・指示文・右側リストの強調が更新される。
- Viewer 左下の **自動同期** チェックを操作できる。
  - ON：現在の Blender フレームを追従する。
  - OFF：その時点で表示中の **ReferenceItem UID** を固定し、Timeline を動かしても別の画像に切り替わらない。
  - OFF 中でも **現在フレームを更新** を押せば、そのフレームの資料へ移る。
  - OFF 中にカテゴリ・Cut・Scene を変更した場合は、新しいコンテキストの現在フレームから資料を選ぶ。
  - ON に戻すと Blender の現在フレームへ追従する。
- Manager 操作中にはライブ状態で入力欄を再描画しない。Viewer から Manager に戻った際は、資料内容が変わった場合だけ更新する。
- Blender 標準の既存ビュアー・登録・画像インポート・D&D 並べ替え・自動スクロール・JSON保存を維持。
- **カメラ重畳チェックと不透明度スライダーはまだ無効**（Phase V-4で接続）。以前の単体POCはこのパッチに組み込まない。

## 通信の仕組み

既存の `requests/*.json` と `responses/*.json` は変更しない。
Blender 側 `manager_external.py` のタイマーで、Scene・フレーム・Cut・カテゴリ・資料一覧などのスナップショットを確認する。
内容が変化した場合のみ、新設する `state/latest.json` にアトミックに書き込む。
Qt 側は Viewer を表示している間だけこのファイルを読み、画像・指示文・強調表示を更新する。
したがって、Qt は **操作コマンドを送信せずに Blender 側から新しい状態を受信**できる。

従来のBlenderタイマー間隔は0.25秒、Qtの確認間隔は0.18秒。そのため**数百ミリ秒程度の遅延があり、24fpsのすべての中間フレームを逐次描画する方式ではない**。今回の検証目的は手動フレーム移動・スクラブに正しく追従すること。高頻度再生時の最適化は必要に応じて後続工程で行う。

## 適用方法

1. Blenderの `.blend` と、作業中の AnimRef JSON を保存。
2. **QtのAnimRefウィンドウとBlender本体を閉じる**。
3. ZIPの `apply_phase_v3.py` と `tests/test_phase_v3_contract.py` を `Blender-Dev` 直下へ展開する（`tests/` も含める）。
4. VSCodeのPowerShellで、リポジトリ直下から実行する。

```powershell
python .\apply_phase_v3.py
python .\tests\test_phase_v3_contract.py
```

5. 既存テストがあれば続けて実行する。V-1／V-2の「同期スイッチは無効」という古い静的判定は、適用時に新仕様へ更新される。

```powershell
python .\tests\test_phase_v2_contract.py
python .\tests\test_phase_v1_contract.py
```

6. 差分を確認する。

```powershell
git diff -- scripts/addons/anim_reference_tool/ tests/ docs/
```

7. Blenderを再起動し、AnimRef ManagerからViewer画面を開く。

パッチはすでにV-3が適用済みなら重複しない。3つのソースファイルが一部だけV-3になっている場合は**安全のため処理を中断**する。適用前のコードは `%TEMP%\animref_backups\phase_v3_...` に保存する。V-2を確認できない場合も上書きしない。

## 実機確認（順に実施）

1. 同じカテゴリで2枚以上の資料を、フレーム範囲をずらして登録しておく（例：1–8f / 9–20f）。
2. Viewerで自動同期をONにする。Blenderの1fから9fへ移動すると、**更新ボタンを押さずに**メイン画像が切り替わる。
3. 切り替えに合わせ、指示文と登録資料一覧の強調が正しく移る。
4. 画像を拡大し、同じ資料のフレーム間を移動する。ズーム・パンが不必要にリセットされない。
5. 自動同期をOFFにし、BlenderのTimelineを大きく動かす。最後の資料が表示されたままになり、ヘッダーに固定フレームが示される。
6. OFFのまま「現在フレームを更新」を押すと、そのフレームの資料を表示する。
7. OFFのままカテゴリを変更し、対応する別カテゴリの資料を確認する。自動同期ONへ戻すと最新フレームに追従する。
8. Blender側で別Cut、別Sceneへ移り、Viewerが古いCut/Sceneの資料を誤表示しない。
9. Managerへ切り替え、エクスプローラーD&D、登録資料の並べ替え・自動スクロール、表示尺・指示文編集、JSON上書き保存が従来どおり動く。
10. 従来のBlender標準ビュアーとViewerの互換性を確認する。画像欠損時はエラー表示になり、Qtが落ちないことを確認する。

## 変更ファイル

- `scripts/addons/anim_reference_tool/operators/manager_external.py`
- `scripts/addons/anim_reference_tool/qt_manager_app.py`
- `scripts/addons/anim_reference_tool/qt_viewer_page.py`
- `tests/test_phase_v1_contract.py` と `tests/test_phase_v2_contract.py` は存在する場合、旧仕様の「スイッチ無効」アサーションのみ更新
- `docs/CURRENT_SPEC.md` / `docs/DEVELOPMENT_LOG.md` は追記

今回は `reference_manager.py`、`project_io.py`、`timeline_manager.py`、`viewer_manager.py`、JSON保存形式には手を加えない。

## 確認済み範囲と注意点

- PASS：Python構文検査、同期ON/OFFと固定表示、シーン・カテゴリ変更、通知ファイルの変更検出・同一内容の再書き込み防止、命令チャネル非干渉、V-1/V-2の回帰テスト。
- **未検証：Blender 5.2 と PySide6 の実画面による今回のV-3の動作**。これはユーザー実機で確認が必要。
- ライブ状態通知に問題がある場合は Blender を開いた状態で、Qt起動に使われた一時フォルダの `state/latest.json` の更新を確認し、Qtの `manager.log` や Blenderコンソールのエラーを確認する。
- Scene切替中や巨大なProjectでは通知の読み込みに失敗する場合がある。この場合は現在フレーム更新を実行し、表示が復旧するか確認する。
