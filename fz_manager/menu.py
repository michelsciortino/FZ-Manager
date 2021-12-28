from typing import Callable
import questionary
from utils import cls
from questionary import Choice


class MenuEntry:
    def __init__(self, name: str, callback: Callable = None, pre_selected: bool = False, ext_index: (int | str) = None,
                 condition=lambda: True):
        self.name = name
        self.callback = callback
        self.pre_selected = pre_selected
        self.ext_index = ext_index
        self.condition = condition


class ActionMenu:
    def __init__(self, title: str, entries: list[MenuEntry], exit_entry: str | list[str] = None, clear_screen: bool = False):
        self.title = title
        self.entries = entries
        self.cls = clear_screen
        self.ext = exit_entry

    async def show(self) -> None:
        while True:
            self.cls and cls()
            choice = await questionary.select(
                self.title,
                [Choice(e.name, e) for e in self.entries if e.condition()],
                qmark='',
                instruction=' '
            ).ask_async(patch_stdout=True)

            if choice is None:
                break

            choice.callback and await choice.callback()

            if isinstance(self.ext, str) and self.ext == choice.name:
                break
            if isinstance(self.ext, list) and choice.name in self.ext:
                break


class SelectMenu:
    def __init__(self, title: str, entries: list[MenuEntry], clear_screen: bool = False, multi_select: bool = False):
        self.title = title
        self.entries = entries
        self.multi = multi_select
        self.cls = clear_screen

    async def show(self) -> (MenuEntry | tuple[list[MenuEntry], list[MenuEntry], list[MenuEntry]] | tuple[None, None, None]):
        self.cls and cls()

        if not self.multi:
            return await questionary.select(
                message=self.title,
                choices=[Choice(e.name, e) for e in self.entries if e.condition()],
                qmark='',
                instruction=' '
            ).ask_async(patch_stdout=True)

        choice = await questionary.checkbox(
            message=self.title,
            choices=[Choice(e.name, e, checked=e.pre_selected) for e in self.entries if e.condition()],
            qmark=''
        ).ask_async(patch_stdout=True)

        if choice is None:
            return None, None, None

        if not self.multi:
            return self.entries[choice]
        else:
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


async def show_message_menu(message):
    return await ActionMenu(message, [MenuEntry('Back')], 'Back').show()
