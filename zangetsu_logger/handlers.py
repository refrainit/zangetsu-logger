import sys
import os
from logging.handlers import RotatingFileHandler


class EnvVarFileHandler(RotatingFileHandler):
    """環境変数でログファイルパスを設定できるRotatingFileHandler"""

    def __init__(
        self, filename, mode="a", maxBytes=0, backupCount=0, encoding=None, delay=False
    ):
        # ファイルパスを解決
        resolved_filename = self._resolve_filename(filename)

        # 親ディレクトリを作成
        os.makedirs(os.path.dirname(resolved_filename), exist_ok=True)

        super().__init__(
            resolved_filename, mode, maxBytes, backupCount, encoding, delay
        )

        # ファイル作成確認とエラーハンドリング
        try:
            if not os.path.exists(resolved_filename) and not delay:
                # 空のファイルを作成してみて、書き込み権限を確認
                with open(resolved_filename, "w"):
                    pass
        except (IOError, PermissionError) as e:
            # エラーをログに記録
            sys.stderr.write(
                f"Failed to create log file {resolved_filename}: {str(e)}\n"
            )
            # コンソールにリダイレクト
            self.stream = sys.stderr

    def _resolve_filename(self, filename):
        """環境変数や絶対/相対パスを考慮してファイル名を解決"""
        # 環境変数 zangetsu_LOG_DIR が設定されていれば使用
        log_dir = os.environ.get("zangetsu_LOG_DIR")

        # 絶対パスの場合はそのまま使用
        if os.path.isabs(filename):
            return filename

        # 環境変数が設定されている場合
        if log_dir:
            return os.path.join(log_dir, filename)

        # デフォルトは実行ディレクトリ
        return os.path.join(os.getcwd(), filename)

    def emit(self, record):
        """ログレコードの出力処理をオーバーライドしてエラーハンドリングを強化"""
        try:
            # 標準的なemit処理
            super().emit(record)
        except Exception as e:
            # エラーを標準エラー出力に出力
            sys.stderr.write(f"Error writing to log file: {str(e)}\n")
            # スタックトレースを出力
            import traceback

            traceback.print_exc(file=sys.stderr)
