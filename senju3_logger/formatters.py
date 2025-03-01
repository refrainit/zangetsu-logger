import logging
import json
from datetime import datetime
import socket
import traceback
import os
import pytz  # 必要に応じてpytzをインストール


class Senju3JsonFormatter(logging.Formatter):
    """日本時間に対応したSenju3形式のJSONフォーマッタ"""

    def __init__(self, fmt=None, datefmt=None, style="%", validate=True):
        super().__init__(fmt, datefmt, style, validate)
        self.hostname = socket.gethostname()
        # 日本のタイムゾーンを設定
        self.jst = pytz.timezone("Asia/Tokyo")

    def format(self, record):
        """レコードをJSON形式にフォーマット（日本時間対応）"""
        log_record = {}

        # 日本時間のタイムスタンプを生成
        current_time = datetime.now(self.jst)
        log_record["timestamp"] = current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["message"] = record.getMessage()
        log_record["hostname"] = self.hostname

        # 追加情報
        if hasattr(record, "filename"):
            log_record["filename"] = record.filename
        if hasattr(record, "funcName") and record.funcName:
            log_record["function"] = record.funcName
        if hasattr(record, "lineno"):
            log_record["line"] = record.lineno

        # スタックトレース情報の追加（エラー時）
        if record.exc_info:
            log_record["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": "".join(traceback.format_exception(*record.exc_info)),
            }

        # 環境変数から追加情報を取得
        for env_var in ["ENVIRONMENT", "SERVICE_NAME", "VERSION"]:
            value = os.environ.get(f"SENJU3_{env_var}")
            if value:
                log_record[env_var.lower()] = value

        # JSONに変換
        try:
            return json.dumps(log_record, default=str, ensure_ascii=False)
        except Exception as e:
            # JSONエンコードに失敗した場合のフォールバック
            error_msg = f"JSON encoding error: {str(e)}"
            print(error_msg)
            return json.dumps(
                {
                    "timestamp": current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "level": "ERROR",
                    "message": record.getMessage(),
                    "error": error_msg,
                },
                ensure_ascii=False,
            )


class Senju3ConsoleFormatter(logging.Formatter):
    """日本時間に対応したコンソール出力用フォーマッタ"""

    def __init__(self, fmt=None, datefmt=None, style="%", validate=True):
        super().__init__(fmt, datefmt, style, validate)
        # 日本のタイムゾーンを設定
        self.jst = pytz.timezone("Asia/Tokyo")

    def format(self, record):
        """レコードをフォーマット（日本時間対応）"""
        # 日本時間のタイムスタンプを生成
        jst_time = datetime.now(self.jst).strftime("%Y-%m-%d %H:%M:%S")

        # レコードに日本時間を追加
        record.jst_time = jst_time

        # 親クラスのformatメソッドを呼び出し
        return super().format(record)