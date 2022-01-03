from typing import Callable, Optional
from inspect import iscoroutinefunction
import questionary
from prompt_toolkit.history import History
from prompt_toolkit.layout import Container
from prompt_toolkit.output import ColorDepth
from questionary import Choice, Question


def __inject__(question: Question, titlebar: Container, erase_when_done: bool):
    question.application.full_screen = True
    question.application.refresh_interval = 1
    question.application._color_depth = ColorDepth.DEPTH_24_BIT
    question.application.erase_when_done = erase_when_done
    if titlebar:
        question.application.layout.container.get_children().insert(0, titlebar)


# noinspection PyProtectedMember
async def load_last_answer(question):
    buffer = question.application.current_buffer
    buffer.load_history_if_not_yet_loaded()
    await buffer._load_history_task
    buffer.history_backward()


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
                 titlebar: Container = None,
                 clear_screen: bool = False):
        self.message = message
        self.entries = entries
        self.choices = [Choice(e.name, e) for e in self.entries if e.condition()]
        self.question = questionary.select(
            self.message,
            self.choices,
            qmark='',
            instruction=' '
        )
        __inject__(self.question, titlebar, clear_screen)

    async def show(self) -> MenuEntry | None:
        if not len(self.choices):
            return None
        if (choice := await self.question.ask_async(patch_stdout=True)) is None:
            return None
        if choice.callback:
            if iscoroutinefunction(choice.callback):
                await choice.callback()
            else:
                choice.callback()
        return choice


class SelectMenu:
    def __init__(self,
                 message: str,
                 entries: list[MenuEntry],
                 default: (int | str) = None,
                 titlebar: Container = None,
                 clear_screen: bool = False):
        self.message = message
        self.entries = entries
        self.default = default
        self.choices: list[Choice] = [Choice(e.name, e) for e in self.entries if e.condition()]
        default = None
        if self.default is not None:
            for c in self.choices:
                if c.value.ext_index == self.default:
                    default = c
                    break
        self.question = questionary.select(
            message=self.message,
            choices=self.choices,
            qmark='',
            instruction=' ',
            default=default
        )
        __inject__(self.question, titlebar, clear_screen)

    async def show(self) -> (MenuEntry | None):
        if not len(self.choices):
            return None
        return await self.question.ask_async(patch_stdout=True)


class CheckboxMenu:
    def __init__(self,
                 message: str,
                 entries: list[MenuEntry],
                 titlebar: Container = None,
                 clear_screen: bool = False):
        self.message = message
        self.entries = entries
        self.choices = [Choice(e.name, e, checked=e.pre_selected) for e in self.entries if e.condition()]
        self.question = questionary.checkbox(
            message=self.message,
            choices=self.choices,
            qmark=''
        )
        __inject__(self.question, titlebar, clear_screen)

    async def show(self) -> (tuple[list[MenuEntry], list[MenuEntry], list[MenuEntry]] | tuple[None, None, None]):
        if not len(self.choices):
            return None, None, None
        if (choice := await self.question.ask_async(patch_stdout=True)) is None:
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
                 titlebar: Container = None,
                 clear_screen: bool = False,
                 load_last_value: bool = False,
                 history: History = None):
        self.message = message
        self.default = default
        self.only_dirs = only_directories
        self.validator = validator
        self.load_last_value = load_last_value
        self.question = questionary.path(
            message=self.message,
            default=self.default,
            qmark='',
            only_directories=self.only_dirs,
            validate=self.validator,
            history=history
        )
        __inject__(self.question, titlebar, clear_screen)

    async def show(self) -> str:
        if self.load_last_value:
            await load_last_answer(self.question)
        return await self.question.ask_async(patch_stdout=True)


class AlertMenu:
    def __init__(self,
                 message,
                 titlebar: Container = None,
                 clear_screen: bool = False):
        self.message = message
        self.menu = ActionMenu(self.message, [MenuEntry('Back')], titlebar=titlebar, clear_screen=clear_screen)

    async def show(self):
        return await self.menu.show()


class InputMenu:
    def __init__(self,
                 message: str,
                 hint: str = None,
                 validator: Optional[Callable[[str], bool]] = lambda p: True,
                 titlebar: Container = None,
                 clear_screen: bool = False,
                 load_last_value: bool = False,
                 history: History = None):
        self.message = message
        self.hint = hint if hint else ''
        self.validator = validator
        self.load_last_value = load_last_value
        self.question = questionary.text(
            message=self.message,
            default=self.hint,
            validate=self.validator,
            qmark='',
            history=history
        )
        __inject__(self.question, titlebar, clear_screen)

    async def show(self):
        if self.load_last_value:
            await load_last_answer(self.question)
        return await self.question.ask_async()
