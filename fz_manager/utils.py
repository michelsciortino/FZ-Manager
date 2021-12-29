import os


class Term:
    @staticmethod
    def cls():
        os.system('cls' if os.name == 'nt' else 'clear')


class Colors:
    FACTORIO_FG = 230, 145, 0
    FACTORIO_BG = 43, 43, 43
    GREEN = 51, 255, 0
    RED = 255, 0, 0
    BLUE = 30, 144, 255
    ORANGE = 255, 165, 0
    END = '\033[0m'
    ENDL = '\033[K'

    @staticmethod
    def fg(rgb: tuple[int, int, int]):
        return f'\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m'

    @staticmethod
    def bg(rgb: tuple[int, int, int]):
        return f'\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m'

    @staticmethod
    def colorize(fg_color: tuple[int, int, int] = None, bg_color: tuple[int, int, int] = None, *text: str, endl=False) -> str:
        if not (fg_color and bg_color):
            return ' '.join(text)
        foreground = Colors.fg(fg_color) if fg_color else ''
        background = Colors.bg(bg_color) if bg_color else ''
        t = ' '.join(text)
        end = Colors.ENDL if endl else Colors.END
        return foreground + background + t + end

    @staticmethod
    def debug(*text: str):
        return Colors.colorize(Colors.BLUE, None, *text)

    @staticmethod
    def info(*text: str):
        return Colors.colorize(Colors.GREEN, None, *text)

    @staticmethod
    def warn(*text: str):
        return Colors.colorize(Colors.ORANGE, None, *text)

    @staticmethod
    def error(*text: str):
        return Colors.colorize(Colors.RED, None, *text)

    @staticmethod
    def factorio(*text: str):
        t = Colors.colorize(Colors.FACTORIO_FG, Colors.FACTORIO_BG, *text, endl=True)
        return t


class String:
    @staticmethod
    def isblank(string: (str | None)):
        return string is None or string.strip() == ''
