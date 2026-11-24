# AnimRef Phase V-5.3.1 — 旧UI整理パッチの安全検査修正

## 症状

`python .\apply_phase_v5_3.py --check` で「V-5.2の機能／登録状態と一致しない」と表示される場合がある。

前版のV-5.3は、V-5.2で要求されていた実際の振る舞いの検査に加えて、`UI_V3_2_LAUNCHER_ONLY` および `UI_V4_CAMERA_OVERLAY` といったパッチのコメント識別子が残っているかまで必須条件にしていた。これらはUI機能の証明にならず、別の改訂・改行・コメント整理を経た同等実装でも拒否され得る。

**この修正版はコメント識別子だけで判定しない。** 代わりに、登録解除、旧Image Editor同期関数の先頭return、Qt起動経路、重畳操作の通信経路などの実際のPythonコード構造を調べる。

## 重要な安全策

- `--check` は読み取り専用。差分や削除対象を表示するだけ。
- 不一致の場合は **失敗項目を個別に表示して中止**する。安全装置を無効化したわけではない。
- 未登録かつ参照されていない旧パネル／旧オペレーターファイル以外は削除しない。
- 既存のQt Viewer / Manager・Timeline同期・カメラ重畳コードは変更しない。
- `--apply` の際は削除／編集対象を `%TEMP%\animref_backups\phase_v5_3_1_...` に退避する。
- Docs追記と `.gitignore` 更新を含む。アドオン機能の仕様は変更しない。
- 診断の不一致を修正するために元ファイルを手作業で消したり、条件行をコメントアウトしたりしない。

## インストール

1. 動作確認済みのローカルコードをGitコミットしておく。BlenderとQt AnimRefを終了する。
2. このZIPを `BlenderDev` ルートに展開する。
3. まずPowerShellで**検査のみ**行う。

```powershell
python .\apply_phase_v5_3_1.py --check
```

PASSの場合、退役予定のファイル名を確認してから実行する。

```powershell
python .\apply_phase_v5_3_1.py --apply
python .\tests\test_phase_v5_3_1_contract.py
python .\tests\test_phase_v5_3_1_installer.py
```

その後Blenderを起動し、Nパネル「AnimRefを開く」→ Qt Viewer / Managerの切替、資料の更新、Timeline同期ON/OFF、カメラ重畳ON/OFFと不透明度、ManagerのD&D・保存、通常Image Editorが勝手に更新されないことを確認する。

## NGだった場合

エラーは `V-5.2の必須条件に不一致` の下に具体的な箇所を表示する。出力全文を共有してくれ。**その時点では削除・変更は発生していない。**

## 注意

古い `apply_phase_v5_3.py` と以前の `test_phase_v5_3_*` はそのまま残る。今回実行するのは `apply_phase_v5_3_1.py` と `test_phase_v5_3_1_*` だ。全ての古いテストが新たなコメント非依存の基準で書かれているわけではないので、古いV-5.3インストーラテストがある場合は、独立した旧版テストとして区別する。

GitHubの `main` にV-5.2以降のローカル変更がまだ反映されていない場合、先に古い `main` を作業フォルダへ上書きしないこと。
