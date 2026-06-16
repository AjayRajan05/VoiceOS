from tools.os_control.platform import get_platform_adapter


class WindowManager:

    def __init__(self, adapter=None):
        self._adapter = adapter or get_platform_adapter()

    def close_window(self):
        return self._adapter.close_active_window()

    def switch_window(self):
        return self._adapter.switch_window()
