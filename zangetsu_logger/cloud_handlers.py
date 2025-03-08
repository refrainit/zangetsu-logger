import io
import logging
import os
import threading
import time
from logging.handlers import MemoryHandler
from typing import List, Optional


class CloudStorageHandler(MemoryHandler):
    """
    クラウドストレージにログをバッチアップロードするための基底クラス

    ログレコードをメモリにバッファし、一定量または一定時間経過後に
    クラウドストレージにアップロードします。
    """

    def __init__(
        self,
        capacity: int = 100,
        flushLevel: int = logging.ERROR,
        flushOnClose: bool = True,
        flush_interval: int = 60,  # 60秒ごとに強制フラッシュ
        formatter: Optional[logging.Formatter] = None,
    ):
        # カスタムtargetを使わずに初期化（後でオーバーライド）
        super().__init__(capacity, flushLevel, None, flushOnClose)

        self.formatter = formatter
        self.flush_interval = flush_interval
        self._buffer_lock = threading.RLock()
        self._last_flush_time = time.time()

        # 定期的なフラッシュを行うタイマースレッドを開始
        if flush_interval > 0:
            self._start_timer()

    def _start_timer(self) -> None:
        """定期的なフラッシュを行うタイマーを開始"""

        def _flush_timer():
            while True:
                time.sleep(self.flush_interval)
                if time.time() - self._last_flush_time >= self.flush_interval:
                    self.flush()

        timer_thread = threading.Thread(target=_flush_timer, daemon=True)
        timer_thread.start()

    def flush(self) -> None:
        """バッファ内のログをクラウドストレージにアップロード"""
        with self._buffer_lock:
            if self.buffer:
                try:
                    self._upload_logs(self.buffer)
                    self.buffer = []
                    self._last_flush_time = time.time()
                except Exception as e:
                    # エラーが発生した場合はエラーログを出力
                    import sys

                    sys.stderr.write(
                        f"Error uploading logs to cloud storage: {str(e)}\n"
                    )
                    import traceback

                    traceback.print_exc(file=sys.stderr)

    def _upload_logs(self, records: List[logging.LogRecord]) -> None:
        """
        ログレコードをクラウドストレージにアップロード（サブクラスで実装）

        Parameters:
        -----------
        records : List[logging.LogRecord]
            アップロードするログレコードのリスト
        """
        raise NotImplementedError("Subclasses must implement _upload_logs")

    def close(self) -> None:
        """ハンドラをクローズする際の処理"""
        if self.flushOnClose:
            self.flush()
        super().close()


class S3Handler(CloudStorageHandler):
    """
    AWS S3にログをアップロードするハンドラ

    boto3ライブラリが必要です。
    """

    def __init__(
        self,
        bucket_name: str,
        key_prefix: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        capacity: int = 100,
        flushLevel: int = logging.ERROR,
        flushOnClose: bool = True,
        flush_interval: int = 60,
        formatter: Optional[logging.Formatter] = None,
    ):
        """
        Parameters:
        -----------
        bucket_name : str
            ログを保存するS3バケット名
        key_prefix : str
            S3オブジェクトのキープレフィックス（例: 'logs/'）
        aws_access_key_id : str, optional
            AWS認証情報（環境変数または IAM ロールで設定可能）
        aws_secret_access_key : str, optional
            AWS認証情報（環境変数または IAM ロールで設定可能）
        aws_region : str, optional
            AWSリージョン（デフォルト: us-east-1）
        capacity : int, default=100
            バッファに保持するログレコードの最大数
        flushLevel : int, default=logging.ERROR
            このレベル以上のログが来たときに強制的にフラッシュする
        flushOnClose : bool, default=True
            ハンドラをクローズするときにフラッシュするかどうか
        flush_interval : int, default=60
            定期的なフラッシュの間隔（秒）
        formatter : logging.Formatter, optional
            ログのフォーマッタ
        """
        super().__init__(capacity, flushLevel, flushOnClose, flush_interval, formatter)

        self.bucket_name = bucket_name
        self.key_prefix = key_prefix.rstrip("/") + "/"
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region or "us-east-1"

        # boto3クライアントの初期化（遅延初期化）
        self._s3_client = None

    @property
    def s3_client(self):
        """S3クライアントの遅延初期化"""
        if self._s3_client is None:
            try:
                import boto3

                # 認証情報が指定されていれば使用、なければデフォルト認証を使用
                if self.aws_access_key_id and self.aws_secret_access_key:
                    self._s3_client = boto3.client(
                        "s3",
                        region_name=self.aws_region,
                        aws_access_key_id=self.aws_access_key_id,
                        aws_secret_access_key=self.aws_secret_access_key,
                    )
                else:
                    self._s3_client = boto3.client("s3", region_name=self.aws_region)

            except ImportError:
                raise ImportError(
                    "boto3 is required for S3Handler. Install it with: pip install boto3"
                )

        return self._s3_client

    def _upload_logs(self, records: List[logging.LogRecord]) -> None:
        """ログレコードをS3にアップロード"""
        if not records:
            return

        # ログをフォーマットしてバッファに格納
        log_buffer = io.StringIO()
        for record in records:
            if self.formatter:
                formatted_record = self.formatter.format(record)
                log_buffer.write(formatted_record)
                log_buffer.write("\n")
            else:
                log_buffer.write(record.getMessage())
                log_buffer.write("\n")

        # タイムスタンプベースのオブジェクトキーを生成
        timestamp = time.strftime("%Y/%m/%d/%H%M%S", time.gmtime())
        random_suffix = os.urandom(4).hex()  # 衝突を避けるためのランダムサフィックス
        key = f"{self.key_prefix}{timestamp}-{random_suffix}.log"

        # S3にアップロード
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=log_buffer.getvalue().encode("utf-8"),
                ContentType="text/plain",
                ContentEncoding="utf-8",
            )
        except Exception as e:
            import sys

            sys.stderr.write(
                f"Failed to upload logs to S3 bucket '{self.bucket_name}': {str(e)}\n"
            )
            raise


class GCSHandler(CloudStorageHandler):
    """
    Google Cloud Storageにログをアップロードするハンドラ

    google-cloud-storageライブラリが必要です。
    """

    def __init__(
        self,
        bucket_name: str,
        blob_prefix: str,
        project_id: Optional[str] = None,
        credentials_file: Optional[str] = None,
        capacity: int = 100,
        flushLevel: int = logging.ERROR,
        flushOnClose: bool = True,
        flush_interval: int = 60,
        formatter: Optional[logging.Formatter] = None,
    ):
        """
        Parameters:
        -----------
        bucket_name : str
            ログを保存するGCSバケット名
        blob_prefix : str
            GCSブロブのプレフィックス（例: 'logs/'）
        project_id : str, optional
            GCPプロジェクトID（環境変数から読み取ることも可能）
        credentials_file : str, optional
            サービスアカウントの認証情報ファイルパス
        capacity : int, default=100
            バッファに保持するログレコードの最大数
        flushLevel : int, default=logging.ERROR
            このレベル以上のログが来たときに強制的にフラッシュする
        flushOnClose : bool, default=True
            ハンドラをクローズするときにフラッシュするかどうか
        flush_interval : int, default=60
            定期的なフラッシュの間隔（秒）
        formatter : logging.Formatter, optional
            ログのフォーマッタ
        """
        super().__init__(capacity, flushLevel, flushOnClose, flush_interval, formatter)

        self.bucket_name = bucket_name
        self.blob_prefix = blob_prefix.rstrip("/") + "/"
        self.project_id = project_id
        self.credentials_file = credentials_file

        # GCSクライアントの初期化（遅延初期化）
        self._storage_client = None
        self._bucket = None

    @property
    def storage_client(self):
        """GCSクライアントの遅延初期化"""
        if self._storage_client is None:
            try:
                from google.cloud import storage
                from google.oauth2 import service_account

                # 認証情報が指定されていれば使用
                if self.credentials_file:
                    credentials = service_account.Credentials.from_service_account_file(
                        self.credentials_file
                    )
                    self._storage_client = storage.Client(
                        project=self.project_id, credentials=credentials
                    )
                else:
                    # デフォルトの認証情報を使用
                    self._storage_client = storage.Client(project=self.project_id)

            except ImportError:
                raise ImportError(
                    "google-cloud-storage is required for GCSHandler. "
                    "Install it with: pip install google-cloud-storage"
                )

        return self._storage_client

    @property
    def bucket(self):
        """GCSバケットの取得"""
        if self._bucket is None:
            self._bucket = self.storage_client.bucket(self.bucket_name)
        return self._bucket

    def _upload_logs(self, records: List[logging.LogRecord]) -> None:
        """ログレコードをGCSにアップロード"""
        if not records:
            return

        # ログをフォーマットしてバッファに格納
        log_buffer = io.StringIO()
        for record in records:
            if self.formatter:
                formatted_record = self.formatter.format(record)
                log_buffer.write(formatted_record)
                log_buffer.write("\n")
            else:
                log_buffer.write(record.getMessage())
                log_buffer.write("\n")

        # タイムスタンプベースのブロブ名を生成
        timestamp = time.strftime("%Y/%m/%d/%H%M%S", time.gmtime())
        random_suffix = os.urandom(4).hex()  # 衝突を避けるためのランダムサフィックス
        blob_name = f"{self.blob_prefix}{timestamp}-{random_suffix}.log"

        # GCSにアップロード
        try:
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(log_buffer.getvalue(), content_type="text/plain")
        except Exception as e:
            import sys

            sys.stderr.write(
                f"Failed to upload logs to GCS bucket '{self.bucket_name}': {str(e)}\n"
            )
            raise
