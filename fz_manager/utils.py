import os


class Term:
    HEAD = '\r\033[K'
    RESET = '\033[0m'
    RESET_FG = '\033[39m'
    RESET_BG = '\033[49m'
    ENDL = '\033[K'
    F_RESET = '\033[0m\033]11;?\a\033[K'

    @staticmethod
    def cls():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def fg(rgb: tuple[int, int, int]):
        return f'\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m'

    @staticmethod
    def bg(rgb: tuple[int, int, int]):
        return f'\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m'

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


class String:
    @staticmethod
    def isblank(string: (str | None)):
        return string is None or string.strip() == ''
