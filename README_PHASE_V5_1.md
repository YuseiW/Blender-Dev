# AnimRef Phase V-5.1: Windows改行によるV-5適用失敗の修正

## 原因
V-4の `apply_phase_v4.py` は `Path.write_text()` により、WindowsではコードがCRLFで保存され得ます。旧V-5の `apply_phase_v5.py` はLFに対する生バイトSHA-256を厳密比較しており、コードが同一でもWindowsではインストールを中止することがありました。旧テストの `AssertionError` はV-5未適用に続く結果です。

## 適用手順
1. 正常動作している `.blend` とソースを保存。BlenderとAnimRef(Qt)を終了する。
2. このZIPを **Blender-Devルート**に展開する（V-5配布物と同じ階層）。
3. PowerShellで下記を実行する。

```powershell
python .\apply_phase_v5_1.py
python .\tests\test_phase_v5_contract.py
python .\tests\test_phase_v4_contract.py
```

- インストーラーは**コード内容を改行差だけ無視してV-4公式版と比較**します。実際の内容が変更されていれば差分を出して中止し、上書きしません。
- 既にV-5が適用済みなら何もしません。バックアップは `%TEMP%\animref_backups\phase_v5_1_...` に作成します。
- `camera_overlay_manager.py` 以外の既存アドオンコード、プロジェクトJSON、Blendファイルを変更しません。
- 引き続きV-5の実機試験は未実施です。特にScene複製、カメラ共有、元背景画像の保護を確認してください。

## 差分エラーの場合
差分出力を共有してください。**手動でハッシュチェックを外したり、V-5ファイルを丸ごとコピーして上書きしないこと**。ユーザー側の変更を保護するためです。
