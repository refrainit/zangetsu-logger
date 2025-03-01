from senju3_logger import initialize

logger = initialize()

logger.debug("デバッグ情報")
logger.info("情報ログ")
logger.warning("警告ログ")
logger.error("エラーログ")
logger.critical("致命的なエラー")
