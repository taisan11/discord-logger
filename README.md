AIくん流石っす
ただ、discord-py-selfの知識が少なめなのと、最新バージョンに追いつけないのはしょうがないよ...
# Discord Logger TUI

Discord メッセージを SQLite3 に保存し、Textual TUI で管理・閲覧するツール。

## 機能

- **チャンネル選択**: Discord サーバーのテキストチャンネルから保存対象を選択
- **メッセージ履歴取得**: レートリミット対応で過去メッセージを取得
- **リアルタイム保存**: WebSocket 経由で来信メッセージを自動保存
- **SQLite3 ストレージ**: すべてのメッセージデータを永続化
  - メッセージ本体（テキスト、編集履歴）
  - 添付ファイル情報
  - 埋め込みメッセージ（embeds）
  - リアクション
  - ユーザー情報
- **簡易ビューワー**: TUI からメッセージを閲覧

## ファイル構成

```
discord-logger/
├── main.py              # エントリーポイント
├── app.py               # Textual TUI アプリケーション
├── db.py                # SQLite3 データベース管理
├── discord_client.py    # Discord クライアント & メッセージ取得
├── pyproject.toml       # パッケージ設定
└── discord_messages.db  # SQLite3 データベース（生成）
```

## インストール

```bash
# プロジェクトディレクトリに移動
cd discord-logger

# パッケージをインストール
uv sync
```

## 設定

`.env` ファイルを作成して Discord トークンを設定：

```env
TOKEN=your_discord_token_here
```

### トークンの取得方法

discord.py-self を使用しているため、ユーザーアカウントトークンが必要です：

1. Discord にログイン
2. ブラウザの開発者ツール（F12）を開く
3. コンソールタブで以下を実行：
   ```javascript
   (function(){const token = document.body.appendChild(document.createElement('iframe')).contentWindow.localStorage.token.split('"')[1];console.log(token)})()
   ```
4. 表示されたトークンを `.env` に記入

## 使用方法

```bash
# アプリケーション起動
python main.py
```

### TUI 操作

- **[S]ync History**: 選択したチャンネルの過去メッセージを取得
- **[V]iew**: メッセージビューワーを更新
- **[R]efresh**: チャンネルリストを更新
- **E[x]it** または **[Q]uit**: アプリケーション終了

### サーバーとチャンネル選択

画面左側に 2 つのカラムが表示されます：

1. **Servers パネル（上）**
   - 接続済みの Discord サーバー一覧
   - サーバーを選択するとチャンネルが読み込まれます
   - 起動時に最初のサーバーが自動選択されます

2. **Channels パネル（下）**
   - 選択されたサーバー内のテキストチャンネル一覧
   - 各チャンネルの保存済みメッセージ数を表示
   - チャンネルをクリックするとメッセージを閲覧できます

### 操作フロー

```
[起動] → Refresh（自動実行）
  ↓
[サーバーを選択] → チャンネル一覧が更新
  ↓
[チャンネルを選択] → メッセージビューワー表示
  ↓
[Sync History] → メッセージ履歴を取得・保存
```

### 画面構成

```
┌─ Discord Message Logger ──────────────┐
├──────────────────────────────────────┤
│ Channels │        Sync Status        │
│          ├──────────────────────────┤
│ #channel │     Message Viewer       │
│ #general │                          │
│ #random  │                          │
├──────────────────────────────────────┤
│ [Sync] [View] [Refresh] [Exit]      │
└──────────────────────────────────────┘
```

## データベーススキーマ

### channels
保存対象のチャンネル情報

- `channel_id`: Discord チャンネルID（主キー）
- `guild_id`: Discord サーバーID
- `channel_name`: チャンネル名
- `parent_channel_id`: 親チャンネルID（スレッド等）
- `channel_type`: チャンネル種別（text/voice/forum/thread など）
- `raw_json`: チャンネルの生データ（圧縮）
- `created_at`: レコード作成日時
- `updated_at`: レコード更新日時

### messages
メッセージ本体（**主要データ**）

- `message_id`: メッセージID（主キー）
- `channel_id`: 外部キー（channels.channel_id）
- `user_id`: メッセージ投稿者のID
- `username`: ユーザー表示名
- `avatar_url`: ユーザーアバターURL
- `content`: メッセージ本文
- `created_at`: 投稿日時
- `edited_at`: 編集日時（編集されていなければ NULL）
- `message_type`: `normal` / `edit` など

### attachments
添付ファイル情報

- `attachment_id`: 添付ファイルID（主キー）
- `message_id`: 外部キー（messages.message_id）
- `filename`: ファイル名
- `url`: ファイルURL
- `size`: ファイルサイズ（バイト）
- `content_type`: MIME タイプ

### embeds
埋め込みメッセージ（リッチメッセージ）

- `embed_id`: 埋め込みID（主キー）
- `message_id`: 外部キー（messages.message_id）
- `title`: タイトル
- `description`: 説明文
- `color`: 色（16進カラーコード）
- `url`: リンク URL
- `timestamp`: タイムスタンプ

### reactions
リアクション情報

- `reaction_id`: リアクションID（主キー）
- `message_id`: 外部キー（messages.message_id）
- `emoji`: 絵文字テキスト
- `count`: リアクション数

### sync_state
同期状態管理

- `channel_id`: 主キー & 外部キー（channels.channel_id）
- `last_message_id`: 最後に同期したメッセージID
- `last_sync_at`: 最後の同期日時
- `sync_status`: `pending` / `syncing` / `completed` / `error`

## 実装の詳細

### レートリミット対応

Discord API には「100メッセージごとに約2秒待つ」という制限があります。本アプリケーションは：

- リクエスト間に 0.5 秒の遅延を挿入
- 100メッセージ（BATCH_SIZE）ごとに 5 倍の遅延（2.5 秒）を追加
- 429 Too Many Requests エラーを回避

```python
REQUEST_DELAY = 0.5  # seconds between requests
BATCH_SIZE = 100     # messages per batch
```

### リアルタイムメッセージ保存

WebSocket 経由で Discord に接続し、以下のイベントをリッスン：

- `on_message`: 新規メッセージ受信
- `on_message_edit`: メッセージ編集
- `on_reaction_add`: リアクション追加

## ログ

ログは `discord_logger.log` に保存されます。ターミナルにも出力されます。

## トラブルシューティング

### "No TOKEN found" エラー

→ `.env` ファイルが存在するか、`TOKEN=` が記入されているか確認

### チャンネルが表示されない

→ アカウントでアクセス可能なチャンネルのみが保存されます
→ サーバーに参加していることを確認

### メッセージ取得が遅い

→ 大量のメッセージを取得する場合、レートリミット対応で時間がかかります
→ `REQUEST_DELAY` を増やすとさらに遅くなりますが、より安全です

### データベースエラー

→ `discord_messages.db` を削除して再実行（すべてのデータが削除されます）

## 今後の拡張予定

- [ ] 検索機能
- [ ] エクスポート（CSV / JSON）
- [ ] バックアップ機能
- [ ] 複数チャンネルの同時同期
- [ ] メディア（画像）プレビュー
- [ ] より詳細なビューワー

## ライセンス

MIT License

## 注意事項

- このツールは **ユーザーアカウント** を使用します
- Discord の ToS で禁止されている用途には使用しないでください
- アカウント情報（トークン）は安全に管理してください
