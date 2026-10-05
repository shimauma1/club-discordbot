# 作業状況

最終更新：2026-10-06（日本時間）

- 大会認証Botを `discordbot/tournament-verification/` に配置。
- 自己紹介の形式は名前・学年・チーム名。投稿後に認証ボタンを押すと大会参加者ロールを付与。
- SQLiteで記録を保持し、再起動後も設置済みボタンを利用可能。
- Discordへの接続、ボタン設置、自己紹介から認証・チャンネル閲覧までユーザー確認済み。
- NASのユーザーサービス `tournament-verification.service` で稼働。自動起動とLinger有効。
- ユーザーの希望により稼働先はNASを維持。外部ホスティングは使用しない。
- 独立Gitリポジトリから `https://github.com/shimauma1/club-discordbot` のmainへ初回送信完了。ユーザー指定の保存先は公開リポジトリ。
- トークン、DB、仮想環境をGitから除外。
