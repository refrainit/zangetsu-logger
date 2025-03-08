import importlib.resources as pkg_resources
import logging
import logging.config
import os
from typing import Any, Dict, Optional

import yaml

from zangetsu_logger.formatters import zangetsuJsonFormatter
from zangetsu_logger.handlers import EnvVarFileHandler


def get_default_config() -> Dict[str, Any]:
    """デフォルトのロガー設定を読み込む"""
    config_text = pkg_resources.read_text(__package__, "default_config.yaml")
    return yaml.safe_load(config_text)


def configure_from_yaml(config_path: str) -> Dict[str, Any]:
    """YAMLファイルからロガー設定を読み込む"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logging.config.dictConfig(config)
    return config


def initialize(
    config_path: Optional[str] = None,
    log_level: Optional[str] = None,
    app_name: Optional[str] = None,
    enable_file_logging: bool = False,
    log_dir: Optional[str] = None,
    cloud_storage: Optional[Dict[str, Any]] = None,
) -> logging.Logger:
    """
    アプリケーションのロガーを初期化する

    Parameters:
    -----------
    config_path : str, optional
        設定ファイルのパス。指定がなければ環境変数 zangetsu_LOGGER_CONFIG かデフォルト設定を使用
    log_level : str, optional
        ロギングレベル。設定ファイルの値を上書きする
    app_name : str, optional
        アプリケーション名。指定がなければパッケージ名が使用される
    enable_file_logging : bool, default=False
        ファイル出力を有効にするかどうか。False の場合は console ハンドラのみ使用
    log_dir : str, optional
        ログファイルを出力するディレクトリ。指定した場合は zangetsu_LOG_DIR 環境変数を上書き
    cloud_storage : dict, optional
        クラウドストレージの設定。以下のキーをサポート:
        - 'type': 's3' または 'gcs'
        - 's3_config': S3用の設定（type='s3'の場合）
          - 'bucket_name': バケット名
          - 'key_prefix': キープレフィックス
          - 'aws_access_key_id': AWSアクセスキー (optional)
          - 'aws_secret_access_key': AWSシークレットキー (optional)
          - 'aws_region': AWSリージョン (optional)
        - 'gcs_config': GCS用の設定（type='gcs'の場合）
          - 'bucket_name': バケット名
          - 'blob_prefix': ブロブプレフィックス
          - 'project_id': GCPプロジェクトID (optional)
          - 'credentials_file': 認証情報ファイルパス (optional)
        - 'flush_interval': フラッシュ間隔（秒）
        - 'capacity': バッファサイズ
        - 'min_level': 最小ログレベル

    Returns:
    --------
    logger : logging.Logger
        設定されたロガーインスタンス
    """
    # ログディレクトリを環境変数にセット（指定されていれば）
    if log_dir:
        os.environ["zangetsu_LOG_DIR"] = log_dir

    # 設定ファイルの読み込み
    if config_path is None:
        config_path = os.environ.get("zangetsu_LOGGER_CONFIG")

    if config_path and os.path.exists(config_path):
        config = configure_from_yaml(config_path)
    else:
        config = get_default_config()

    # ファイル出力を無効化する場合の処理
    if not enable_file_logging:
        # ロガー定義をループしてファイルハンドラを削除
        for logger_name, logger_config in config.get("loggers", {}).items():
            handlers = logger_config.get("handlers", [])
            # コンソールハンドラのみを保持する
            logger_config["handlers"] = [h for h in handlers if h == "console"]

        # ルートロガーにも同様の処理
        if "root" in config:
            handlers = config["root"].get("handlers", [])
            config["root"]["handlers"] = [h for h in handlers if h == "console"]

    # コンソールハンドラのログレベルを調整
    if "handlers" in config and "console" in config["handlers"]:
        if log_level:
            level = getattr(logging, log_level.upper(), logging.DEBUG)
            config["handlers"]["console"]["level"] = level

    # 既存のハンドラをクリア（重複を防ぐため）
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 設定を適用
    logging.config.dictConfig(config)

    # アプリケーション名の決定
    if app_name is None:
        import inspect

        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        if module:
            app_name = module.__name__.split(".")[0]
        else:
            app_name = "zangetsu"

    # ロガーの取得とログレベルの設定
    logger = logging.getLogger(app_name)

    # 既存のハンドラがあれば削除（重複を防ぐため）
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    if log_level:
        level = getattr(logging, log_level.upper(), None)
        if level is not None:
            logger.setLevel(level)

    # ロガーの取得とログレベルの設定
    logger = logging.getLogger(app_name)

    if enable_file_logging:
        # app_logハンドラを追加
        app_log_path = os.path.join(
            os.environ.get("zangetsu_LOG_DIR", os.getcwd()), "zangetsu_app.log"
        )
        file_handler = EnvVarFileHandler(
            app_log_path, maxBytes=10485760, backupCount=5, encoding="utf8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(zangetsuJsonFormatter())
        logger.addHandler(file_handler)

        # error_logハンドラを追加
        error_log_path = os.path.join(
            os.environ.get("zangetsu_LOG_DIR", os.getcwd()), "zangetsu_error.log"
        )
        error_handler = EnvVarFileHandler(
            error_log_path, maxBytes=10485760, backupCount=5, encoding="utf8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(zangetsuJsonFormatter())
        logger.addHandler(error_handler)

    # クラウドストレージハンドラの設定
    if cloud_storage:
        storage_type = cloud_storage.get("type")
        if storage_type == "s3":
            _setup_s3_handler(logger, cloud_storage)
        elif storage_type == "gcs":
            _setup_gcs_handler(logger, cloud_storage)
        else:
            logger.warning(f"Unknown cloud storage type: {storage_type}")

    return logger


def _setup_s3_handler(logger, cloud_storage):
    """S3ハンドラをセットアップする"""
    from zangetsu_logger.cloud_handlers import S3Handler

    s3_config = cloud_storage.get("s3_config", {})
    if not s3_config.get("bucket_name"):
        logger.error("S3 bucket_name is required for S3 cloud storage")
        return

    # S3ハンドラを設定
    s3_handler = S3Handler(
        bucket_name=s3_config.get("bucket_name"),
        key_prefix=s3_config.get("key_prefix", "logs/"),
        aws_access_key_id=s3_config.get("aws_access_key_id"),
        aws_secret_access_key=s3_config.get("aws_secret_access_key"),
        aws_region=s3_config.get("aws_region"),
        capacity=cloud_storage.get("capacity", 100),
        flushLevel=getattr(
            logging, cloud_storage.get("min_level", "ERROR").upper(), logging.ERROR
        ),
        flush_interval=cloud_storage.get("flush_interval", 60),
        formatter=zangetsuJsonFormatter(),
    )

    # 最小ログレベルを設定
    min_level = getattr(
        logging, cloud_storage.get("min_level", "DEBUG").upper(), logging.DEBUG
    )
    s3_handler.setLevel(min_level)

    # ロガーにハンドラを追加
    logger.addHandler(s3_handler)
    logger.info(
        f"S3 cloud storage handler added for bucket: {s3_config.get('bucket_name')}"
    )


def _setup_gcs_handler(logger, cloud_storage):
    """Google Cloud Storageハンドラをセットアップする"""
    from zangetsu_logger.cloud_handlers import GCSHandler

    gcs_config = cloud_storage.get("gcs_config", {})
    if not gcs_config.get("bucket_name"):
        logger.error("GCS bucket_name is required for GCS cloud storage")
        return

    # GCSハンドラを設定
    gcs_handler = GCSHandler(
        bucket_name=gcs_config.get("bucket_name"),
        blob_prefix=gcs_config.get("blob_prefix", "logs/"),
        project_id=gcs_config.get("project_id"),
        credentials_file=gcs_config.get("credentials_file"),
        capacity=cloud_storage.get("capacity", 100),
        flushLevel=getattr(
            logging, cloud_storage.get("min_level", "ERROR").upper(), logging.ERROR
        ),
        flush_interval=cloud_storage.get("flush_interval", 60),
        formatter=zangetsuJsonFormatter(),
    )

    # 最小ログレベルを設定
    min_level = getattr(
        logging, cloud_storage.get("min_level", "DEBUG").upper(), logging.DEBUG
    )
    gcs_handler.setLevel(min_level)

    # ロガーにハンドラを追加
    logger.addHandler(gcs_handler)
    logger.info(
        f"GCS cloud storage handler added for bucket: {gcs_config.get('bucket_name')}"
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    名前付きロガーを取得する

    Parameters:
    -----------
    name : str, optional
        ロガー名。指定がなければルートロガーを返す

    Returns:
    --------
    logger : logging.Logger
        ロガーインスタンス
    """
    return logging.getLogger(name)
