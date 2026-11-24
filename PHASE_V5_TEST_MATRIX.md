# AnimRef Phase V-5 — 統合試験表

実施者：＿＿＿＿　Blenderバージョン：＿＿＿＿　Python：＿＿＿＿　実施日：＿＿＿＿

事前準備： `.blend`、JSON、参照画像、Gitリポジトリをバックアップする。旧POCカメラ背景画像は解除する。**テストには複製した `.blend` を使用**し、保存の成否を確認するまで実データを上書きしない。

各項目に **PASS / FAIL / 未実施** を記載し、FAILなら操作手順・表示メッセージ・再現頻度を記録する。

| No. | 試験項目 | 操作 / 期待結果 | 結果 |
|---|---|---|---|
| 01 | Viewer / Manager切替 | 同一ウィンドウで切替。Managerの入力・選択状態が勝手に初期化されない | 未実施 |
| 02 | 登録・保存・再読込 | 画像複数枚のExplorer D&D、登録、並べ替え、自動スクロール、JSON上書きと再読込 | 未実施 |
| 03 | カテゴリ切替 | 原画 / レイアウト / 絵コンテの一覧と表示画像・指示が一致 | 未実施 |
| 04 | Timeline境界 | 資料境界の前・ちょうど・後（例8f/9f）で画像・指示・強調表示が一致 | 未実施 |
| 05 | 自動同期ON/OFF | OFFでViewer・カメラ重畳保持。ONで現在フレームに追従 | 未実施 |
| 06 | カット切替 | ViewerからCut変更、Managerも同じCut。元のScene Timelineは意図せず移動しない | 未実施 |
| 07 | カメラ重畳 | ON/OFFと透明度0/50/100、元のユーザー背景画像が保持される | 未実施 |
| 08 | Scene切替 | 別Sceneに切替、ViewerのScene/Cut/画像が追従。旧Scene資料が誤表示されない | 未実施 |
| 09 | Scene複製・別カメラ | Sceneを複製し専用Cameraデータを使う。両Sceneで重畳の識別が衝突しない | 未実施 |
| 10 | Scene複製・共有カメラ | 共有CameraデータでSceneを切替。表示中Sceneの重畳だけが残り、元の背景は消えない | 未実施 |
| 11 | 画像欠損 | 参照画像の一時リネーム後、Viewerは欠損を表示し、Blenderで例外連発・操作不能にならない | 未実施 |
| 12 | カメラなし・カメラ切替 | カメラ解除 / 別Cameraへ切替し、適切に非表示・再表示。ユーザー背景を保持 | 未実施 |
| 13 | 終了・再起動 | Qtを閉じて再起動、Blenderを再起動、`.blend` を再読み込みして状態復元 | 未実施 |
| 14 | 旧ビュアーとの干渉 | 旧Image EditorビュアーとQt Viewerを開閉し、表示・同期・終了でクラッシュがない | 未実施 |
| 15 | 長時間使用 | 20〜30分、Timelineスクラブ・画面切替・重畳操作を反復し固まらない | 未実施 |
| 16 | 最終レンダリング | 重畳ONでレンダリングし、画像にリファレンスが合成されない | 未実施 |

## コード契約テスト

```powershell
python .\tests\test_phase_v5_contract.py
python .\tests\test_phase_v4_contract.py
python .\tests\test_phase_v3_2_contract.py
python .\tests\test_phase_v3_1_contract.py
python .\tests\test_phase_v3_contract.py
python .\tests\test_phase_v2_contract.py
python .\tests\test_phase_v1_contract.py
```

## Blender診断（読み取り専用）

Blender Scripting > Text Editor > Open で `tools/phase_v5_diagnostics.py` を開き、Run Script。結果はシステムコンソールで確認する。

- `duplicate_scene_owner_tokens` が0であるか（複製直後は引き継いだ旧トークンが残る場合がある。重畳有効化後に一意化される）。
- `shared_camera_count` が1以上なら、Scene間で同じCameraデータを共有している。Sceneごとの同時独立表示はできない。
- `orphan_animref_slots` が1以上なら、以前のSceneの重畳が残っている可能性がある。保存前に状況を確認する。
- `missing_images_total` はファイルの移動・削除を示す。画像パスは名前のみを表示する。

**重要：** これらの模擬テストがPASSしても、Blender 5.2本体とPySide6の実機試験がすべてPASSしたことを意味しない。実機試験が完了するまでPhase V-5を「完了」にしない。
