from src.config.settings import LoggingConfig


def test_log_file_is_off_by_default() -> None:
    # Container-safe default: a file sink must be opted into, never assumed.
    assert LoggingConfig().file_path is None
