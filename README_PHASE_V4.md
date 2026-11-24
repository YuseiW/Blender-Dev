# AnimRef — Phase V-4 カメラ重畳本体統合

対象: **Phase V-3.2 の実機確認を終えた `Blender-Dev` ローカル作業ツリー**（Blender 5.2、PySide6）。

## 今回追加したもの

- Qt Viewer 左下の「カメラ重畳」スイッチを有効化。
- Qt Viewer の「不透明度」0〜100%スライダーを有効化。初期値50%。マウス操作中の値を120ms間隔でまとめ、要求を順次Blenderへ送信。
- Blenderのカメラ背景画像（Front/FIT）へ、Viewerのカット・カテゴリ・フレームに対応する画像を表示。**表示はカメラビュー（テンキー0）で確認する。**
- Viewerの自動同期ON: 重畳画像もTimelineへ追従。OFF: 同じカット・カテゴリでは最後に表示した画像を保持。手動更新、カット・カテゴリの切替では更新。
- Viewer/Manager間の移動、既存Managerの資料登録・D&D・JSON保存、旧独立ビュアーは維持。
- ユーザー自身が設定したカメラ背景画像は削除しない。AnimRefが追加したレイヤーだけをタグで識別して削除し、解除後はCameraの背景表示設定を元に戻す。
- Cameraの表示は**Viewportの補助表示のみ**で、最終レンダリングへの合成はしない。

設定はBlenderのSceneプロパティ `animref_overlay_enabled`, `animref_overlay_opacity` に保持する。AnimRef ProjectのJSON保存形式は変更しない。旧3D Nパネルは起動ボタンのみ。

## 重要: 以前の単体試験を終了する

以前の `camera_overlay_poc.py` を同じBlenderセッションで実行した場合、試験用背景画像と今回のAnimRef背景画像は**別々に存在する**。POCのNパネルから「OFF（解除）」で試験レイヤーを取り除いた後、Blenderを終了して本体パッチを適用すること。すでにBlenderを再起動しPOC未使用なら不要。

## 導入手順

1. `.blend` と変更中のプロジェクトを保存する。`git status` を確認し、V-3.2の正常動作状態をコミットすることを推奨。
2. BlenderとPySide6のAnimRefアプリを完全に終了する。
3. ZIPを **`Blender-Dev` のルート**へ展開する（`apply_phase_v4.py` がルート直下に来るように）。
4. PowerShellを `Blender-Dev` で開いて実行する。

```powershell
python .\apply_phase_v4.py
python .\tests\test_phase_v4_contract.py
python .\tests\test_phase_v3_2_contract.py
python .\tests\test_phase_v3_1_contract.py
python .\tests\test_phase_v3_contract.py
python .\tests\test_phase_v2_contract.py
python .\tests\test_phase_v1_contract.py
```

5. Blenderを完全に再起動する。3DビューのNパネル「AnimRef」から「AnimRefを開く」。
6. Qt Viewer側で「原画」などを選び、Blenderの**アクティブカメラ**が設定されていることを確認する。
7. `テンキー0` でカメラビューに入り、Viewer左下の「カメラ重畳」をONにする。
8. 不透明度50%で半透明表示を確認し、スライダーを動かす。Timelineを資料の切替境界を跨いで動かす。

パッチは変更対象のバックアップを `%TEMP%\animref_backups\phase_v4_日時` に保存する。変更箇所が期待したV-3.2のコードと違う場合は書き換えず停止する。再実行は追加変更せず終了する。

## テスト項目（実機で確認する）

1. カメラ重畳ONで、カメラビューに選択中資料が半透明表示される。
2. 不透明度を0%→50%→100%に変更して表示が変わる。
3. 画像に対応するフレーム境界を跨いでTimelineを動かすと、画像・指示文・カメラ重畳が一致する。
4. 自動同期OFFでViewerと重畳が最後の画像に固定される。ONで現在フレームへ戻る。
5. Viewerのカット・カテゴリ切替で重畳画像も切り替わる。
6. 重畳OFFでAnimRefの画像だけ消える。もともと設定されていた別のカメラ背景画像は残る。
7. Manager画面への切替と画像登録・並べ替え・保存が従来どおり動く。
8. BlenderとQtを閉じて再起動した後も、必要な場合に重畳を利用できる。

## 制約・次工程

- カメラ背景画像の表示方法は **FIT**。元画像の縦横比を維持し、余白が出る場合がある。位置・拡大率の細かな調整はV-5以降の検討対象。
- カメラオブジェクトがない場合、重畳は表示できない。正しい画像ファイルがない場合にも重畳を解除してエラー表示・状態通知ができる構造だ。
- 2つのSceneが**同一のCameraデータブロック**を共有する特殊な構成では、背景画像レイヤーも共有される。Scene切替を含む複数SceneテストはPhase V-5で確認する。
- 設定は `.blend` 内のSceneに保持し、AnimRefの外部JSONには含めない。
- 今回のコード検査・模擬テストは成功済みだが、Blender 5.2+PySide6を組み合わせた**V-4本体の実機動作は未確認**。結果を受けてV-5へ進む。
- 古いBlender Image Editorビュアーはこの段階では削除しない。

## 変更するファイル

- `scripts/addons/anim_reference_tool/qt_viewer_page.py`
- `scripts/addons/anim_reference_tool/qt_manager_app.py`
- `scripts/addons/anim_reference_tool/operators/manager_external.py`
- `scripts/addons/anim_reference_tool/timeline_manager.py`
- `scripts/addons/anim_reference_tool/camera_overlay_manager.py`（新規）
- 存在する場合 `tests/test_phase_v1_contract.py`, `test_phase_v2_contract.py`, `test_phase_v3_contract.py`（古い静的判定をV-4対応へ修正）
- 存在する場合 `docs/CURRENT_SPEC.md`, `docs/DEVELOPMENT_LOG.md`（V-4経過を追記）

データ構造・外部JSON・`project_io.py`・`reference_manager.py`・画像登録フローには変更を加えない。
