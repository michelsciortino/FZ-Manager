from typing import Callable, Optional
import questionary
from utils import Term
from questionary import Choice


class MenuEntry:
    def __init__(self,
                 name: str,
                 callback: Callable = None,
                 pre_selected: bool = False,
                 ext_index: (int | str) = None,
                 condition: Optional[Callable[[], bool]] = lambda: True
                 ):
        self.name = name
        self.callback = callback
        self.pre_selected = pre_selected
        self.ext_index = ext_index
        self.condition = condition


class ActionMenu:
    def __init__(self,
                 message: str,
                 entries: list[MenuEntry],
                 clear_screen: bool = False,
                 header: str = None
                 ):
        self.message = message
        self.entries = entries
        self.cls = clear_screen
        self.header = header

    async def show(self) -> MenuEntry | None:
        if self.cls:
            Term.cls()
        if self.header:
            print(self.header)

        choices = [Choice(e.name, e) for e in self.entries if e.condition()]
        if not len(choices):
            return None
        choice = await questionary.select(
            self.message,
            choices,
            qmark='',
            instruction=' '
        ).ask_async(patch_stdout=True)

        if choice is None:
            return None

        choice.callback and await choice.callback()
        return choice


class SelectMenu:
    def __init__(self,
                 message: str,
                 entries: list[MenuEntry],
                 default: (int | str) = None,
                 clear_screen: bool = False,
                 header: str = None
                 ):
        self.message = message
        self.entries = entries
        self.cls = clear_screen
        self.default = default
        self.header = header

    async def show(self) -> (MenuEntry | None):
        if self.cls:
            Term.cls()
        if self.header:
            print(self.header)
        choices: list[Choice] = [Choice(e.name, e) for e in self.entries if e.condition()]
        if not len(choices):
            return None
        default = None
        if self.default is not None:
            for c in choices:
                if c.value.ext_index == self.default:
                    default = c
                    break

        return await questionary.select(
            message=self.message,
            choices=choices,
            qmark='',
            instruction=' ',
            default=default
        ).ask_async(patch_stdout=True)


class MultiSelectMenu:
    def __init__(self,
                 message: str,
                 entries: list[MenuEntry],
                 clear_screen: bool = False,
                 header: str = None):
        self.message = message
        self.entries = entries
        self.cls = clear_screen
        self.header = header

    async def show(self) -> (tuple[list[MenuEntry], list[MenuEntry], list[MenuEntry]] | tuple[None, None, None]):
        if self.cls:
            Term.cls()
        if self.header:
            print(self.header)

        choices = [Choice(e.name, e, checked=e.pre_selected) for e in self.entries if e.condition()]
        if not len(choices):
            return None, None, None

        choice = await questionary.checkbox(
            message=self.message,
            choices=choices,
            qmark=''
        ).ask_async(patch_stdout=True)

        if choice is None:
            return None, None, None

        selected: list[MenuEntry] = choice
        added: list[MenuEntry] = []
        removed: list[MenuEntry] = []
        for entry in self.entries:
            if entry in choice:
                if not entry.pre_selected:
                    added.append(entry)
            elif entry.pre_selected:
                removed.append(entry)
        return selected, added, removed


class PathMenu:
    def __init__(self,
                 message: str,
                 default: str = '',
                 only_directories: bool = False,
                 validator: Optional[Callable[[str], bool]] = lambda p: True,
                 clear_screen: bool = False,
                 header: str = None):
        self.message = message
        self.cls = clear_screen
        self.default = default
        self.only_dirs = only_directories
        self.validator = validator
        self.header = header

    async def show(self) -> str:
        if self.cls:
            Term.cls()
        if self.header:
            print(self.header)
        return await questionary.path(
            message=self.message,
            default=self.default,
            qmark='',
            only_directories=self.only_dirs,
            validate=self.validator
        ).ask_async(patch_stdout=True)


class AlertMenu:
    def __init__(self,
                 message,
                 clear_screen: bool = False,
                 header: str = None):
        self.message = message
        self.cls = clear_screen
        self.header = header

    async def show(self):
        if self.cls:
            Term.cls()
        if self.header:
            print(self.header)
        return await ActionMenu(self.message, [MenuEntry('Back')], 'Back').show()


class InputMenu:
    def __init__(self,
                 message: str,
                 hint: str = None,
                 validator: Optional[Callable[[str], bool]] = lambda p: True,
                 clear_screen: bool = False,
                 header: str = None):
        self.message = message
        self.hint = hint if hint else ''
        self.validator = validator
        self.cls = clear_screen
        self.header = header

    async def show(self):
        if self.cls:
            Term.cls()
        if self.header:
            print(self.header)
        return await questionary.text(
            message=self.message,
            default=self.hint,
            validate=self.validator,
            qmark=''
        ).ask_async()
