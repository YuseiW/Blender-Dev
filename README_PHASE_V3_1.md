# AnimRef Phase V-3.1 — Timeline同期の補完・Viewerカット選択

対象: Phase V-3適用済みの `Blender-Dev` ローカル作業ツリー。過去のV-1/V-2を再適用する必要はありません。

## 修正内容

- V-3のQtライブ通知（`state/latest.json`）が停止・欠落しても、従来の `snapshot` 要求/応答で現在のBlenderフレームを再取得。Viewer表示中のみ、ライブ通知に更新がなければ約0.75秒間隔で補完ポーリング（通常の応答遅延が別途発生）。
- Qt Viewerの右側に **カット選択** を追加。ManagerとBlenderに共通の `active_cut_index` を使用し、既存 `select_cut` コマンドで変更する。
- 補完ポーリング中にユーザーが切り替え操作をした場合、先行するポーリング応答の直後に実行する。Managerの編集中の入力欄は自動更新で描画し直さない。
- Viewer下部に現在使用した同期経路（「ライブ通知」または「Snapshot補完」）を表示する。
- Blenderアドオンのデータ構造・Managerの資料登録・JSON形式は変更しない。カメラ重畳本体への接続はPhase V-4のまま。

## 導入手順

1. Blenderと外部Qt Viewer/Managerを閉じる。念のため `git status` で現状を確認し、可能ならコミットまたは別のバックアップを作る。
2. 本ZIPを **`Blender-Dev` リポジトリのルート** に展開する（`apply_phase_v3_1.py` がルート直下に来るように）。
3. リポジトリのルートで次を実行:

```powershell
python .\apply_phase_v3_1.py
python .\tests\test_phase_v3_1_contract.py
python .\tests\test_phase_v3_contract.py
python .\tests\test_phase_v2_contract.py
python .\tests\test_phase_v1_contract.py
```

4. Blenderを再起動し、「資料管理ツールを開く」からQt Viewer/Managerを起動。Viewerへ切り替える。
5. Viewerの「自動同期」が**ON**であることを確認する。BlenderのTimelineを動かし、画像・指示文・強調表示が変わるか試す。
6. Viewer右側の「カット」欄で別のカットを選び、Managerと同じカットになっているか確認する。
7. Viewerの自動同期をOFFにしてフレーム移動しても表示が固定されること、再度ONで追従が再開することを確認する。
8. Managerに戻って登録・並べ替え・保存の基本操作ができるか確認する。

## もし同期しない場合

- **Viewerの下部**に「同期経路：ライブ通知（V-3.1）」または「同期経路：Snapshot補完（V-3.1）」が表示されるか確認。
- Viewerの「現在フレームを更新」ボタンで更新されるか確認。
- BlenderのPython Consoleに次を入力し、実際のアドオン実行場所とV-3のブリッジ関数がロードされているか確認:

```python
import sys
[(name, mod.__file__, hasattr(mod, '_publish_viewer_state')) for name, mod in sys.modules.items() if name.endswith('.manager_external')]
```

返り値が `False` の場合は、BlenderがPhase V-3以前の `manager_external.py` を読み込んでいる可能性がある。適用先リポジトリとBlenderがロードしているアドオンの場所が同じか確認する。

パッチは自動的に元ファイルのバックアップを `%TEMP%\animref_backups\phase_v3_1_...` に作成する。再実行しても二重に追加しない。

## 検証状況

自動テスト: V-3.1の通知欠落・snapshot復旧・カット選択予約、V-1/V-2/V-3回帰を確認。Blender 5.2 / Windows上での実機動作は未検証。原因の最終確定には実機ログが必要。
