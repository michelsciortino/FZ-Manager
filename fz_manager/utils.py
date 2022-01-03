import asyncio
import os
import threading
import inspect


class Term:
    HEAD = '\r\x1B[K'
    RESET = '\x1B[0m'
    RESET_FG = '\x1B[39m'
    RESET_BG = '\x1B[49m'
    ENDL = '\x1B[K'
    F_RESET = '\x1B[0m\x1B]11;?\a\x1B[K'

    @staticmethod
    def cls():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def fg(rgb: tuple[int, int, int]):
        return f'\x1B[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m'

    @staticmethod
    def bg(rgb: tuple[int, int, int]):
        return f'\x1B[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m'

    @staticmethod
    def colorize(fg_color: tuple[int, int, int] = None,
                 bg_color: tuple[int, int, int] = None,
                 *text: str,
                 sep: str = ' ',
                 end: str = RESET) -> str:
        if not fg_color and not bg_color:
            return ' '.join(text)
        foreground = Term.fg(fg_color) if fg_color else ''
        background = Term.bg(bg_color) if bg_color else ''
        t = sep.join(text)
        return background + foreground + t + end

    @staticmethod
    def debug(*text: str):
        return Term.colorize(Colors.BLUE, None, *text)

    @staticmethod
    def info(*text: str):
        return Term.colorize(Colors.GREEN, None, *text)

    @staticmethod
    def warn(*text: str):
        return Term.colorize(Colors.ORANGE, None, *text)

    @staticmethod
    def error(*text: str):
        return Term.colorize(Colors.RED, None, *text)


class Colors:
    FACTORIO_FG = 230, 145, 0
    FACTORIO_BG = 43, 43, 43
    GREEN = 51, 255, 0
    RED = 255, 0, 0
    BLUE = 30, 144, 255
    ORANGE = 255, 165, 0

    @staticmethod
    def rgb_to_hex(rgb: tuple[int, int, int]):
        def clamp(x):
            return max(0, min(x, 255))

        return f'#{clamp(rgb[0]):02x}{clamp(rgb[1]):02x}{clamp(rgb[2]):02x}'

    FACTORIO_FG_HEX = rgb_to_hex(FACTORIO_FG)
    FACTORIO_BG_HEX = rgb_to_hex(FACTORIO_BG)


class String:
    @staticmethod
    def isblank(string: (str | None)):
        return string is None or string.strip() == ''


class Thread(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None):
        self._target = target
        self._args = args
        if kwargs is None:
            kwargs = {}
        self._kwargs = kwargs
        self._return = None
        super().__init__(group, target, name, args, kwargs)
        self._alive = True

    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)
            if inspect.iscoroutinefunction(self._target):
                self._return = asyncio.run(self._return)
        self._alive = False

    def join(self, **kwargs) -> any:
        super().join(**kwargs)
        return self._return

    def is_alive(self) -> bool:
        return self._alive


async def run_on_thread(fn, *args):
    t = Thread(target=fn, args=args)
    t.start()
    while t.is_alive():
        await asyncio.sleep(0.5)
    return t.join()
