import os
import logging
import logging.config
import yaml
import importlib.resources as pkg_resources
from typing import Dict, Any, Optional

from senju3_logger.formatters import Senju3JsonFormatter
from senju3_logger.handlers import EnvVarFileHandler


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
) -> logging.Logger:
    """
    アプリケーションのロガーを初期化する

    Parameters:
    -----------
    config_path : str, optional
        設定ファイルのパス。指定がなければ環境変数 SENJU3_LOGGER_CONFIG かデフォルト設定を使用
    log_level : str, optional
        ロギングレベル。設定ファイルの値を上書きする
    app_name : str, optional
        アプリケーション名。指定がなければパッケージ名が使用される
    enable_file_logging : bool, default=False
        ファイル出力を有効にするかどうか。False の場合は console ハンドラのみ使用
    log_dir : str, optional
        ログファイルを出力するディレクトリ。指定した場合は SENJU3_LOG_DIR 環境変数を上書き

    Returns:
    --------
    logger : logging.Logger
        設定されたロガーインスタンス
    """
    # ログディレクトリを環境変数にセット（指定されていれば）
    if log_dir:
        os.environ["SENJU3_LOG_DIR"] = log_dir

    # 設定ファイルの読み込み
    if config_path is None:
        config_path = os.environ.get("SENJU3_LOGGER_CONFIG")

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
            app_name = "senju3"

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
            os.environ.get("SENJU3_LOG_DIR", os.getcwd()), "senju3_app.log"
        )
        file_handler = EnvVarFileHandler(
            app_log_path, maxBytes=10485760, backupCount=5, encoding="utf8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(Senju3JsonFormatter())
        logger.addHandler(file_handler)

        # error_logハンドラを追加
        error_log_path = os.path.join(
            os.environ.get("SENJU3_LOG_DIR", os.getcwd()), "senju3_error.log"
        )
        error_handler = EnvVarFileHandler(
            error_log_path, maxBytes=10485760, backupCount=5, encoding="utf8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(Senju3JsonFormatter())
        logger.addHandler(error_handler)

    return logger


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
