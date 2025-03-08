# zangetsu-logger

zangetsu のロギング関連のライブラリ

## このライブラリをインストールして使用する方法

```bash
pip install git+https://github.com/refrainit/zangetsu-logger.git
```

## 環境変数の設定

ロギング設定は環境変数で制御できます。`.env`ファイルや`export`コマンドで以下の環境変数を設定できます：

```bash
zangetsu_LOG_DIR=<ログファイルの出力ディレクトリ>
```

## ライブラリの更新

```bash
pip install --upgrade git+https://github.com/refrainit/zangetsu-logger.git
```

## 使い方

### 基本的な使用方法

```python
from zangetsu_logger import initialize

# 基本的な初期化
logger = initialize()
logger.info("アプリケーションを開始しました")

# カスタム設定での初期化する場合
logger = initialize(
    config_path='/path/to/custom/config.yaml',  # カスタム設定がある場合
    log_level='DEBUG',  # ロギングレベルを DEBUG に設定
    app_name='my_app',  # アプリケーション名を指定
    enable_file_logging=True,  # ファイルへのログ出力を有効化
    log_dir='/path/to/logs'  # デフォルトはカレントディレクトリ
)
```

### 名前付きロガーの取得

```python
from zangetsu_logger import get_logger

# モジュール固有のロガーを取得
module_logger = get_logger('my_module')
module_logger.debug("デバッグメッセージ")
```

## `initialize()` 関数の引数詳細

| 引数名                | デフォルト値 | 説明                           | 設定例と効果                                                                                                                                              |
| --------------------- | ------------ | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config_path`         | `None`       | カスタム設定ファイルのパス     | `/path/to/logging_config.yaml` を指定すると、デフォルト設定の代わりにそのファイルから設定を読み込みます                                                   |
| `log_level`           | `None`       | ロギングレベル                 | `'DEBUG'`: すべてのログを出力<br>`'INFO'`: 情報レベル以上のログを出力<br>`'WARNING'`: 警告レベル以上のログを出力<br>`'ERROR'`: エラーレベルのログのみ出力 |
| `app_name`            | `None`       | アプリケーション名             | 指定しない場合、呼び出し元のモジュール名が使用されます。特定の名前を付けることで、ロガーを明示的に識別できます                                            |
| `enable_file_logging` | `False`      | ファイルへのログ出力を有効化   | `True`: `zangetsu_app.log` と `zangetsu_error.log` にログを出力<br>`False`: コンソール出力のみ                                                            |
| `log_dir`             | `None`       | ログファイルの出力ディレクトリ | `/var/log/myapp` などを指定すると、指定したディレクトリにログファイルを出力                                                                               |

## 開発者向け

### ライブラリ更新手順

```toml
# pyproject.toml
version = "x.x.x" # バージョンを更新
```

```bash
git add .
git commit -m "バージョンを更新"
git tag x.x.x
git push origin master --tags
```
