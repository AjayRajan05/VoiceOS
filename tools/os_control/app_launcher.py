from tools.os_control.platform import get_platform_adapter


class AppLauncher:

    def __init__(self, adapter=None):
        self._adapter = adapter or get_platform_adapter()

    def open_app(self, app_name, args=None):
        result = self._adapter.open_app(app_name, args)
        if result.get("success"):
            return result.get("message", f"Opening {app_name}")
        return f"Failed to open {app_name}: {result.get('error', 'unknown error')}"
