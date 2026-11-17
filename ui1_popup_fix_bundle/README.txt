AnimRef UI-1 — 独立ウィンドウ修正パッチ

原因:
  旧UI-1は bpy.ops.workspace.duplicate() を利用しており、
  独立したOSウィンドウではなくBlender上部のワークスペースタブを追加していた。

目的:
  bpy.ops.wm.window_new_main() を使って独立したBlenderウィンドウを開く。
  メイン画面を変更せず、新しいウィンドウに左=資料登録 / 右=画像プールを配置。
  既存の独立リファレンスビュアーはそのまま維持する。

適用（前回UI-1パッチを導入済みであること）:
  1. zipを展開し、ui1_popup_fix_bundleフォルダとfix_ui1_window.pyを
     Blender-Devリポジトリ直下に配置する。
  2. VSCodeターミナルで python .\fix_ui1_window.py
  3. git diff で変更確認
  4. Blender作業ファイルを保存して終了、Blenderを再起動
  5. 既存のLayoutタブに戻ってから、3DビューのAnimRefタブを開く
  6. 「AnimRef Manager（別ウィンドウ）」を押す

期待する動作:
  - 新しいOSウィンドウが1つ開く
  - その中だけで左の登録パネル・右の画像プールを表示
  - 元のLayoutは変化しない
  - もう一度押しても別ウィンドウは増えない
  - 作業用の独立リファレンスビュアーは従来どおり動作

注意:
  Blender 5.2でのUI実機動作は未確認。
  LayoutにあるVIEW_3Dと右側PROPERTIESが必要。
  旧パッチが作成した「AnimRef Manager」タブは残る。
  修正後の動作確認が済んだら、旧タブを手動で削除してよい。
  画面の右側は旧LayoutのProperties領域を流用するため、
  上部Outlinerとの境界調整は後続UI工程で扱う。

エラーが起きたら、Blenderのエラー表示とウィンドウの状態を教えてください。
