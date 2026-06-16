"""Legacy web UI server hook (not used — VoiceOS is CLI-only)."""

import logging
import os
import threading

logger = logging.getLogger(__name__)


def start_web_server(host: str = "127.0.0.1", port: int = 8000) -> threading.Thread:
    """Launch legacy embedded UI server in a daemon thread (deprecated; CLI-only product)."""

    def _run():
        try:
            configure_process_environment()
            from helpers.ui_server import UiServerRuntime
            from helpers.server_startup import StartupMonitor, run_uvicorn_with_retries

            runtime = UiServerRuntime.create()
            runtime.register_http_routes()
            runtime.register_transport_handlers()

            def build_asgi(startup_monitor):
                return runtime.build_asgi_app(startup_monitor)

            run_uvicorn_with_retries(
                host=host,
                port=port,
                build_asgi_app=build_asgi,
                flush_callback=lambda msg: logger.info(msg),
                access_log=runtime.access_log_enabled(),
            )
        except Exception as e:
            logger.error("Web server failed: %s", e)

    thread = threading.Thread(target=_run, daemon=True, name="voiceos-web")
    thread.start()
    logger.info("Web UI starting at http://%s:%s", host, port)
    return thread


def configure_process_environment() -> None:
    import logging as _logging
    import os as _os
    import time as _time
    _logging.getLogger().setLevel(_logging.WARNING)
    _os.environ["TZ"] = "UTC"
    _os.environ["TOKENIZERS_PARALLELISM"] = "false"
    if hasattr(_time, "tzset"):
        _time.tzset()
