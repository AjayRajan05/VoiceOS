from tools.os_control.app_launcher import AppLauncher
from tools.os_control.keyboard_control import KeyboardControl
from tools.os_control.window_manager import WindowManager
from tools.os_control.clipboard_tool import ClipboardTool
from tools.os_control.platform import get_platform_adapter


class OSToolRouter:

    def __init__(self, system_integration=None, adapter=None):
        self._adapter = adapter or get_platform_adapter()
        self.app = AppLauncher(self._adapter)
        self.keyboard = KeyboardControl(self._adapter)
        self.window = WindowManager(self._adapter)
        self.clipboard = ClipboardTool()
        self.system_integration = system_integration

    def _resolve_app(self, name: str) -> str:
        return self._adapter.resolve_app(name or "")

    def execute(self, tool, args):
        args = args or {}

        if tool == "open_app":
            app = self._resolve_app(args.get("app") or args.get("target") or args.get("input", ""))
            extra_args = []
            file_path = args.get("file") or args.get("path")
            if file_path:
                extra_args.append(str(file_path))
            return self.app.open_app(app, extra_args or None)

        if tool == "type_text":
            text = args.get("text") or args.get("target") or args.get("input", "")
            window = args.get("window") or args.get("app") or args.get("focus")
            if window and self.system_integration:
                import asyncio
                try:
                    asyncio.get_event_loop().run_until_complete(
                        self.system_integration.execute_application_operation(
                            self._resolve_app(window), "focus"
                        )
                    )
                except RuntimeError:
                    asyncio.run(
                        self.system_integration.execute_application_operation(
                            self._resolve_app(window), "focus"
                        )
                    )
            return self.keyboard.type_text(text, window_title=window)

        if tool == "press_key":
            return self.keyboard.press_key(args.get("key", "enter"))

        if tool == "close_window":
            return self.window.close_window()

        if tool == "close_app":
            app = args.get("app") or args.get("target", "")
            if self.system_integration:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        return {"success": True, "message": f"Close requested for {app}"}
                    return loop.run_until_complete(
                        self.system_integration.execute_application_operation(app, "close")
                    )
                except RuntimeError:
                    return asyncio.run(
                        self.system_integration.execute_application_operation(app, "close")
                    )
            return self.window.close_window()

        if tool == "switch_window":
            return self.window.switch_window()

        if tool == "set_clipboard":
            return self.clipboard.set_clipboard(args.get("text", ""))

        if tool == "copy":
            text = self.clipboard.copy_text()
            return f"Copied: {text[:100]}" if text else "Clipboard empty."

        if tool == "paste":
            import pyperclip
            text = pyperclip.paste()
            if text:
                return self.keyboard.type_text(text)
            return "Nothing to paste."

        if tool == "click":
            import pyautogui
            x = args.get("x")
            y = args.get("y")
            if x is not None and y is not None:
                pyautogui.click(x, y)
            else:
                pyautogui.click()
            return "Clicked."

        if tool == "scroll":
            import pyautogui
            direction = (args.get("direction") or args.get("target") or "down").lower()
            amount = int(args.get("amount", 3))
            if direction == "up":
                pyautogui.scroll(amount)
            elif direction == "down":
                pyautogui.scroll(-amount)
            elif direction == "left":
                pyautogui.hscroll(-amount)
            elif direction == "right":
                pyautogui.hscroll(amount)
            return f"Scrolled {direction}."

        if tool == "screenshot":
            import pyautogui
            path = args.get("path", "workspace/screenshot.png")
            pyautogui.screenshot(path)
            return f"Screenshot saved to {path}"

        if tool == "focus_app":
            app = self._resolve_app(args.get("app") or args.get("target", ""))
            if self.system_integration:
                import asyncio
                try:
                    return asyncio.get_event_loop().run_until_complete(
                        self.system_integration.execute_application_operation(app, "focus")
                    )
                except RuntimeError:
                    return asyncio.run(
                        self.system_integration.execute_application_operation(app, "focus")
                    )
            result = self._adapter.focus_window(app)
            if result.get("success"):
                return result.get("message", f"Focused {app}")
            return f"Focus failed for {app}: {result.get('error', 'unknown')}"

        return "Unknown OS action."
