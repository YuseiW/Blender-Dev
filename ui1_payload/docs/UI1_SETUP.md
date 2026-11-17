# AnimRef Manager — UI-1 セットアップ

対象: Blender 5.2 / `YuseiW/Blender-Dev` の Phase 2-A 完了版
状態: UI-1のコードを準備。Blender実機テストは未実施。

## 目的

`week3` の図を基準として「左＝資料登録」「右＝画像プール」の管理画面を追加する。
既存の `Layout`、独立ビュアー、JSON、Projectデータモデルは変更しない。

## インストール

1. このパッチZIPの内容を `Blender-Dev` リポジトリ直下に展開する。
2. VSCodeのターミナルで `python apply_ui1.py` を実行する。
3. `git diff -- scripts/addons/anim_reference_tool/ docs/` で差分を確認する。
4. `.blend` を保存してBlenderを再起動する（アドオンの新規登録が必要）。

## 起動

1. Blender標準の `Layout` ワークスペースを選ぶ。右側にPropertiesエディターがある状態が必要。
2. 3Dビューの `N` キーでサイドバーを開き、`AnimRef` の「AnimRef Managerを開く」を押す。
3. `AnimRef Manager` ワークスペースが作成され、元の `Layout` はそのまま残る。
4. 左の大きい領域は `Properties > Scene`（資料登録）。右のProperties領域は `Properties > Render`（画像プール）。
5. 右側の既存Outlinerが邪魔なら、複製された `AnimRef Manager` 内でだけ境界をドラッグして調整する。
6. 元の3Dビューへは画面上部の `Layout` ワークスペースタブをクリックして戻る。

**注意**: 初回自動レイアウトは既存Layoutの画面分割を利用する。このため右画像プールの高さは、元のProperties領域と同じ。`week3`の完全な幅・高さとサムネイルはUI-2以降で詰める。

## UI-1で可能なこと

- 既存のCut作成・削除、資料種別選択
- 右の画像リストから画像を選択し、左の登録順へ追加
- 資料順序の上下移動、削除、尺と指示の編集
- プロジェクト保存・読み込み
- `Layout` とのワークスペース切り替え

## UI-1でまだ実装しないこと

- 2列サムネイルと画像枠色（UI-2）
- 画像プールから登録枠へのD&D（UI-4）
- `week3` 図2の独立した大プレビュー画面（UI-5）
- Blender外部のWindows GUI

## テスト

1. 元の `Layout` のUIが変わらない。
2. `AnimRef Manager` のタブが一つだけ作られる（ボタンを2度押す）。
3. 左にCut/Category/登録資料一覧、右に画像プールが表示される。
4. 画像を取り込み、右で選択して左に追加できる。
5. 上下移動・削除・尺/指示文編集が働く。
6. 保存・読み込みで登録内容を復元できる。
7. 元の独立ビュアーの同期が正常。
8. `.blend` を保存して再度開いた後も画面と資料が維持される。

動作しない場合は例外と、Blenderの画面スクリーンショットを報告。
