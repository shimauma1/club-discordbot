# Discord大会サーバー・認証Bot

部内向けのシンプルなPython / discord.py製Botです。

参加 → `#はじめに` → `#自己紹介`へ投稿 → 認証ボタン → `🟣大会参加者`ロール付与。

## 動作

- 指定の自己紹介チャンネルへの通常投稿・返信を自己紹介済みと判定します。内容の審査はしません。
- Bot・Webhook・システム通知・スレッド内投稿は対象外です。
- SQLiteにサーバーID・チャンネルID・ユーザーID・記録日時を保存します。本文は保存しません。
- 再起動後も記録と設置済みボタンが使えます。
- 記録がない場合、ボタン押下時に過去の投稿を確認します。導入前やBot停止中の投稿も対象です。
- 履歴確認は最大45秒。通信・権限エラーは未投稿とは区別し、ロールを付与しません。
- 認証結果は押した本人だけに表示します。認証済みなら重複付与しません。
- 一度記録された自己紹介は、投稿を削除しても有効です。退出・再参加でも保持します。
- ロールを手動で外しても再認証できます。参加禁止の管理にはDiscord側のBAN等を使ってください。

## 自己紹介テンプレート

`#自己紹介` では次の形式を案内します。認証は投稿の有無で判定し、各項目の記入内容は審査しません。

```text
名前：
学年：
チーム名：
```

## 1. Discord側の準備

1. [Discord Developer Portal](https://discord.com/developers/applications)でアプリを作成し、Botトークンを取得します。
2. OAuth2の招待URLを作成します。スコープは `bot` と `applications.commands`、Bot権限は「チャンネルを見る」「メッセージを送信」「メッセージ履歴を読む」「ロールの管理」。対象サーバーへ招待します。
3. サーバーのロール設定で **Botロールを「🟣大会参加者」より上** に移動します。参加者ロールに管理者権限は付けません。
4. Botには `#はじめに` の閲覧・送信、`#自己紹介` の閲覧・履歴閲覧を許可します。カテゴリ権限の上書きも確認してください。
5. Discordの「ユーザー設定 → 詳細設定 → 開発者モード」を有効にして、サーバー・2つのチャンネル・参加者ロールのIDをコピーします。

特権Intent（Message Content / Server Members / Presence）は不要です。一般メンバーには `#自己紹介` の投稿を許可し、`#はじめに` の投稿は管理者・Botだけにします。通常カテゴリは参加者ロールで閲覧できるようDiscord側で設定してください。

## 2. NASで初回起動

Python 3.11以上が必要です。このNASでは専用 `.venv` を作成済みです。別の環境では次の手順で準備します。

```bash
cd /home/shimauma/mydata/discordbot/tournament-verification
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

`.env` のトークンと4つのIDを実際の値に置き換えてください。トークンはチャットやGitHubに貼らず、このファイルだけに入力します。外部サービスでは環境変数に設定します。

| 変数 | 値 |
| --- | --- |
| `DISCORD_TOKEN` | Botトークン（アプリのClient Secretではありません） |
| `GUILD_ID` | 大会サーバーID |
| `INTRO_CHANNEL_ID` | `#自己紹介` のID |
| `WELCOME_CHANNEL_ID` | `#はじめに` のID |
| `PARTICIPANT_ROLE_ID` | `🟣大会参加者` のロールID |
| `DATABASE_PATH` | 通常は `data/bot.sqlite3` |

起動します。

```bash
.venv/bin/python bot.py
```

Discordでサーバー管理者が `/setup_verification` を一度実行すると、設定した `#はじめに` に認証ボタンが投稿されます。再実行すると新しいメッセージが増えるため、不要な古いメッセージは手動で削除してください。再起動時の設置し直しは不要です。

停止は `Ctrl+C`。コマンドが見つからない場合はサーバーID、招待スコープ、Botの接続ログを確認してください。

## 3. NASで常時起動（systemd）

### このNASで現在稼働している設定

ユーザーサービス `tournament-verification.service` を登録済みです。ログアウト後も動く設定（Linger）が有効で、NAS起動時に起動します。以下で状態・ログを確認できます。

```bash
systemctl --user status tournament-verification
journalctl --user -u tournament-verification -n 50 --no-pager
```

設定変更後の再起動と停止は次のコマンドを使います。

```bash
systemctl --user restart tournament-verification
systemctl --user stop tournament-verification
```

自動起動も解除する場合は `systemctl --user disable --now tournament-verification` を実行します。設定元は `deploy/tournament-verification.user.service` です。

### 別環境でシステムサービスとして登録する場合

以下は代替手順です。このNASのユーザーサービスと二重起動しないでください。

初回動作確認後、手動起動したBotを停止します。`deploy/discordbot.service` はこのNASのユーザー・保存先向けの例です。別環境では `User` とパスを変更してください。

データフォルダを作り、サービスを登録して起動します（sudo権限が必要）。

```bash
cd /home/shimauma/mydata/discordbot/tournament-verification
mkdir -p data
sudo cp deploy/discordbot.service /etc/systemd/system/discordbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now discordbot
```

状態とログを確認します。

```bash
systemctl status discordbot
journalctl -u discordbot -n 50 --no-pager
```

停止する場合は次を実行します。

```bash
sudo systemctl disable --now discordbot
```

NASの電源とインターネット接続が続いている間だけ動作します。このシステムサービス方式の登録は行っていません（このNASでは上記のユーザーサービスを使用）。

Dockerがある環境では、代わりに以下で起動できます。systemdと同時には起動しないでください。

```bash
docker compose up -d --build
docker compose logs --tail 50
```

## 4. GitHubへの保存とNAS運用

このBotフォルダを独立したGitリポジトリとして管理します。親の `mydata` リポジトリとは別です。GitHubへの送信先は接続後に設定します。

BotはNASのユーザーサービスで常時起動しています。GitHubに送信しても稼働先は変わらず、コード更新も自動反映されません。NASの電源・インターネット接続が必要です。

`.env`、`data/`（参加者の記録）、`.venv/` はGit管理外です。トークンはNASの `.env` に保持します。GitHubはコードのバックアップであり、DBのバックアップにはなりません。

GitHubへ接続した後は、Botフォルダで変更を確認し、必要なファイルだけを記録して送信します。

```bash
cd /home/shimauma/mydata/discordbot/tournament-verification
git status
git diff
```

外部ホスティング向けの設定例も同梱していますが、現在の運用では使用しません。

## 5. 外部ホスティング

GitHubはコードの保管先にして、常駐処理はNASまたは外部ホスティングで動かします。GitHub Actionsでの常駐は行いません。**Botは1インスタンスだけ**で稼働させ、移行時はNAS側を停止します。

### Railway

- GitHubリポジトリを接続し、同梱の `Dockerfile` と `railway.json` を使用します。
- `.env.example` の各値をサービスのVariablesへ設定します。
- **Volumeを作成して `/app/data` にマウント**し、`DATABASE_PATH=/app/data/bot.sqlite3` とします。VolumeはJSONだけでは作成されません。
- レプリカは1、Serverlessによる休止は無効にします。公開ドメイン・HTTPポートは不要です。

### Render

- GitHubリポジトリからBlueprintを作成し、同梱 `render.yaml` を使用します。
- Background Workerと永続Diskを使います。トークンと4つのIDを入力してください。
- この例は有料構成です。適用時に現行プラン・料金を確認してください。
- Webサービスとして起動したり、HTTPヘルスチェック用のポートを追加する必要はありません。

どちらもコンテナの一時領域にDBを置くと再デプロイ時に消えるため、永続領域が必要です。既存記録の移行はBotを停止してDBをコピーしてください。NASと外部側で同じDBを同時に共有しないでください。

公式資料：[discord.py Intent](https://discordpy.readthedocs.io/en/stable/intents.html)、[永続ボタンの例](https://github.com/Rapptz/discord.py/blob/master/examples/views/persistent.py)、[Railway Volume](https://docs.railway.com/volumes)、[Render Disk](https://render.com/docs/disks)、[Render Blueprint](https://render.com/docs/blueprint-spec)。設定例は実デプロイ未検証です。

## 検証・バックアップ

Discordに接続せず、記録の永続化、認証条件、ロール設定、過去投稿の確認などをテストします。

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

実サーバーでは一般メンバーで「未投稿→拒否」「投稿→認証」「再起動→既存ボタンが動作」「停止中の投稿→認証」を確認してください。

バックアップはBot停止中に `data/` をコピーします。DBはローカルディスクまたはホスティングの永続ディスクに置き、SMB/NFS共有上で直接稼働させないでください。自己紹介チャンネルIDを変えた場合、旧チャンネルの記録は新チャンネルの認証には使われません。
