
### Phase 2-A 実装状況

- Blender標準の別ウィンドウ生成: 動作確認済み
- 専用ビュアーへの画像同期: 動作確認済み
- 指示文とフレーム情報の表示: 動作確認済み
- アドオン再有効化後のビュアー識別: 動作確認済み
- .blendファイル切替: 動作確認済み
- 複数Sceneの表示対象分離: 実装中
## 2026-11-10
### Phase 2-A / Step 4-2 実装結果

状態: 完了（ユーザー動作確認）

#### 検証内容
[PASS] test_A.blendの資料表示
[PASS] test_B.blendへの切り替え
[PASS] ファイル間で資料が混在しない
[PASS] ビュアーの重複起動防止
[PASS] test_A.blendへの復帰
[PASS] Timeline同期と既存Image Editorの動作

結果: 全6項目成功

#### 判断
- 現行方式でファイル切替は正常動作
- load_postによる復旧処理は追加しない
- 不必要なウィンドウ再生成処理を避ける

### Phase 2-A / Step 4-3 実装前チェック

状態: 実装開始・動作未確認

#### 仕様確認
- CURRENT_SPEC.md: 確認済み
- DECISIONS.md: 確認済み
- DEVELOPMENT_LOG.md: 確認済み

#### GitHub
確認コミット: 7e9494f
Step 2以降のローカル変更: 未Push

#### 今回の目標
- 複数Sceneを安全に扱う
- 別Sceneによるビュアーの上書きを防止
- 表示Scene変更時に古い画像を残さない
- 既存のTimeline同期を維持する

#### 変更予定ファイル
- timeline_manager.py
- image_manager.py
- viewer_manager.py

#### 変更対象外
- properties.py
- project_io.py
- JSON形式
- ReferenceItemのフレーム計算

#### 完了条件
- Scene AとBを区別できる
- 他Sceneのフレーム更新で表示が変わらない
- 表示対象Sceneを切り替えられる
- 資料がないSceneで古い画像が残らない
- 単一Sceneでも従来どおり動作する

## 2026-11-10
### Phase 2-A / Step 4-1 実装結果

状態: 完了（ユーザー動作確認）

#### 変更内容
- ビュアー識別方法をScreen属性へ変更
- Pythonグローバル変数への依存を削減
- ビュアーの重複起動防止
- Image Editorの消失状態を検出

#### 動作テスト
[PASS] ビュアーの新規生成
[PASS] 重複起動防止
[PASS] 画像・指示文・Timeline同期
[PASS] ウィンドウを閉じて再生成
[PASS] アドオン再有効化後の認識
[PASS] Image Editor変更時の重複防止

結果: 全6項目成功

#### GitHub
確認コミット: 7e9494f
ローカル変更: 未Push


### Phase 2-A / Step 4-2 実装前チェック

状態: 検証開始・結果未確認

#### 仕様確認
- CURRENT_SPEC.md: 確認済み
- DECISIONS.md: 確認済み
- DEVELOPMENT_LOG.md: 確認済み

#### 目的
Blenderファイル切替時の安定性確認。

#### 検証対象
- 別の.blendファイルを開く
- ビュアーの識別状態
- 画像・指示文の更新
- ファイル間での資料混在
- ビュアーの再起動
- 既存データの保持

#### 今回の方針
先に既存コードの動作を検証する。
問題が確認された部分だけ修正する。

#### 変更しないもの
- Projectデータモデル
- JSON形式
- ReferenceItemのフレーム計算

#### 次の作業
テスト結果に基づいて、
必要ならload_postによる復旧処理を実装する。

### Phase 2-A / Step 4-1 実装前チェック

状態: 修正案提示・動作未確認

#### 仕様確認
- CURRENT_SPEC.md: 確認済み
- DECISIONS.md: 確認済み
- 前回の開発ログ: 確認済み

#### GitHub
- 確認コミット: 7e9494f
- Step 2・3のローカル変更: 未push

#### 目標
- ビュアーの識別情報をScreenに保持
- Pythonモジュールの再読み込みに対応
- 閉じられたウィンドウへの参照を防止
- Image Editorが失われた状態を検出

#### 変更対象
- viewer_manager.py

#### 変更対象外
- データ構造
- JSON保存・読み込み
- Timeline同期の計算
- 指示文表示の処理

#### 完了条件
- ウィンドウ識別が正常
- 重複起動が発生しない
- 従来の同期処理が正常
- 再読み込み後もビュアーを識別

#### 次の作業
Step 4-2:
Blenderファイル切替時の安全性検証

## 2026-11-10
### Phase 2-A / Step 3 実装結果

状態: 完了（ユーザー動作確認）

#### 変更ファイル
- ui/viewer_panel.py（新規）
- ui/__init__.py
- viewer_manager.py

#### 実装内容
- Image Editor専用の情報パネル
- カット名・資料種別の表示
- 現在フレームと資料表示範囲の表示
- 作画・演出指示の表示
- 長い日本語指示文の折り返し
- 資料なし・画像欠損時の情報表示

#### 動作テスト
[PASS] 画像と情報パネルの同時表示
[PASS] カット名・種別・フレーム範囲
[PASS] 指示文の表示
[PASS] フレーム変更による更新
[PASS] カット・カテゴリ変更による更新
[PASS] 長い日本語指示文の折り返し
[PASS] 資料なしフレームの表示
[PASS] 通常Image Editorへの非干渉

結果: 全8項目成功

#### 既知の制約
- ビュアー識別にPython内の一時情報を使用
- Auto Sync OFF時は画像と情報が異なる可能性
- Blenderファイル切替・複数Sceneは未検証
- GitHubへのコード反映は未確認

#### 次の工程
Phase 2-A / Step 4:
ビュアーの安定化

## 2026-11-10
### Phase 2-A / Step 2 実装結果

状態: 完了（ユーザー動作確認）

#### 実装内容
- 専用ビュアーへの画像同期
- 通常Image Editorとの表示先分離
- ビュアー起動直後の現在フレーム同期
- 対応資料がない場合の画像表示解除

#### 動作テスト
[PASS] ビュアー起動時の画像表示
[PASS] Timeline自動同期
[PASS] カット変更時の同期
[PASS] 資料カテゴリ変更時の同期
[PASS] 通常Image Editorへの非干渉
[PASS] 資料なしフレームの画像解除
[PASS] ウィンドウを閉じた後の再起動

結果: 全7項目成功

#### 確認状況
Blender上でユーザーが確認。
GitHubへのStep 2コード反映は未確認。

### Phase 2-A / Step 3 実装前チェック

状態: 未実装

#### 仕様確認
- CURRENT_SPEC.md: 確認済み
- DECISIONS.md: 確認済み
- DEVELOPMENT_LOG.md: 確認済み

#### 目的
独立ビュアーに画像・指示文・資料情報を表示する。

#### 変更予定ファイル
- ui/viewer_panel.py（新規）
- ui/__init__.py
- viewer_manager.py

#### 変更しないファイル
- properties.py
- project_io.py
- timeline_manager.py
- image_manager.py

#### 完了条件
- 現在のカット名と資料種別を表示
- 現在フレームと資料の表示範囲を表示
- 画像に対応する指示文を表示
- 長い指示文を折り返して表示
- フレーム変更時に指示文が切り替わる
- 対応資料なしの場合に適切な情報を表示
- 通常のImage Editorへ影響しない

## 2026-11-10
### Phase 2-A / Step 1 動作確認結果

状態: 完了（ユーザー確認）

- 別ウィンドウ生成: PASS
- Image Editorへの切り替え: PASS
- 重複起動防止: PASS
- 閉じた後の再表示: PASS

原因と修正:
area_dupli() の呼び出しに
'INVOKE_DEFAULT' を指定した。

### Phase 2-A / Step 2 実装前チェック

状態: 未実装・テスト待ち

確認したGitHubコミット: 7e9494f
ローカルの修正: 未push分あり

目的:
専用ビュアーが開いている間は、
そのImage Editorのみを同期対象とする。

変更予定:
- image_manager.py
- viewer_manager.py
- operators/viewer.py

変更しないもの:
- properties.py
- project_io.py
- timeline_manager.py
- JSON形式

完了条件:
- ビュアーに現在の画像が表示される
- 通常のImage Editorを変更しない
- カット・カテゴリ・フレーム変更に追従
- 対応資料なしの場合は画像を解除
- ビュアーを閉じてもエラーにならない

### Phase 2-A / Step 1 不具合調査

確認コミット: 7e9494f
状態: 修正案提示・再テスト待ち

問題:
「ビュアーを開く」を押しても
別ウィンドウが表示されない。

コード上の原因:
screen.area_dupli() を
EXEC_DEFAULTで呼び出していた。

修正:
bpy.ops.screen.area_dupli('INVOKE_DEFAULT')

確認状況:
GitHub上のコードを確認。
Blender上での修正後テストは未実施。

次の作業:
ウィンドウ生成、Image Editorへの変更、
重複起動防止、再起動処理の確認。

## 2026-11-10
### Phase 2-A / Step 1 実装前チェック

状態: 実装開始・動作未確認

#### 仕様確認
- CURRENT_SPEC.md: 確認済み
- DECISIONS.md: 確認済み
- DEVELOPMENT_LOG.md: 確認済み

#### GitHub確認
- main: 1ee89cd
- ローカルの未push変更: 未確認

#### 今回の目標
- Blender標準の別ウィンドウを生成
- 新しいウィンドウをImage Editorにする
- 同一セッションでの重複起動を防止
- 既存のBlender操作を維持する

#### 変更予定ファイル
- viewer_manager.py（新規）
- operators/viewer.py（新規）
- operators/__init__.py（変更）
- ui/main_panel.py（変更）

#### 今回は変更しないもの
- データ構造
- JSON保存形式
- Timeline同期処理

#### 完了条件
- ビュアーを開ける
- 2回押してもウィンドウが増殖しない
- 閉じた後に再度開ける
- 既存のアドオンが正常動作する

# DEVELOPMENT_LOG
# Blender Animation Reference Tool

## 2026-11-10
### Phase 1完了・Phase 2開始前

GitHub確認コミット:
eec9c64459ccddc6c5015021d1abd4186ad18ac0

### 実装済み機能

- 画像インポート
- Image Pool
- カット管理
- 資料登録・削除・並び替え
- 尺・指示文の入力
- JSON保存・読み込み
- Timeline自動同期
- カット・カテゴリ変更時の同期
- 資料なしフレームの表示解除
- データ検証
- 読み込み失敗時のロールバック

### テスト結果

ユーザーがBlender上で実行。

[PASS] テストデータ作成
[PASS] JSON保存
[PASS] JSON読み込み・復元
[PASS] フレーム範囲検索
[PASS] 不正JSONの拒否・状態保持
[PASS] 欠損画像を含むJSONの読込

=== ALL TESTS PASSED ===

UI最終確認：全項目成功（ユーザー報告）

### 既知の問題

1. Windowsコンソールの日本語文字化け
2. chcp 65001実行後にBlenderがフリーズ
3. 全Image Editorが自動同期対象になる

### 未実装

- 専用リファレンスビュアー
- ビュアー専用の表示先管理
- 独立ウィンドウでの指示文表示
- カメラビューへの資料重畳表示
- 画像差し替え

### 次の実装

Phase 2-A:
Blender標準の独立ウィンドウを生成する。

完了条件:
- 別ウィンドウを生成できる
- Image Editorへ切り替えられる
- 既存のBlender操作が正常に動く


---

## 実装前チェック用テンプレート

### 日付：
### 対象機能：

#### 仕様確認
- CURRENT_SPEC.md確認：
- DECISIONS.md確認：
- 前回の開発ログ確認：

#### コード確認
- GitHubコミット：
- ローカルとの差分：
- 既存の関連機能：

#### 今回の作業
- 変更予定ファイル：
- 実装する機能：
- 変更しない機能：

#### 完了条件
- 動作確認項目：
- 想定される問題：

#### 状態
未着手 / 作業中 / 完了 / 保留


---

## 実装後ログ用テンプレート

### 日付：
### 対象機能：

#### 変更ファイル

#### 実装内容

#### 動作テスト
- 成功：
- 失敗：
- 未確認：

#### 発生した問題

#### 対処内容

#### 設計変更の有無

#### Gitコミット

#### 次のタスク
