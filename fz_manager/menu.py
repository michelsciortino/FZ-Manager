from typing import Callable
import questionary
import os

from questionary import Choice


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


class MenuEntry:
    def __init__(self, name: str, callback: Callable = None, pre_selected: bool = False, ext_index: (int | str) = None):
        self.name = name
        self.callback = callback
        self.pre_selected = pre_selected
        self.ext_index = ext_index


class ActionMenu:
    def __init__(self, title: str, entries: list[MenuEntry], exit_entry: str | list[str] = None, clear_screen: bool = False):
        self.title = title
        self.entries = entries
        self.cls = clear_screen
        self.ext = exit_entry

    def show(self) -> None:
        while True:
            self.cls and cls()
            choice = questionary.select(
                self.title,
                [Choice(e.name, e) for e in self.entries],
                qmark='',
                instruction=' '
            ).ask()

            if choice is None:
                break

            choice.callback and choice.callback()

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

    def show(self) -> (MenuEntry | tuple[list[MenuEntry], list[MenuEntry], list[MenuEntry]] | tuple[None, None, None]):
        self.cls and cls()

        if not self.multi:
            return questionary.select(
                message=self.title,
                choices=[Choice(e.name, e) for e in self.entries],
                qmark='',
                instruction=' '
            ).ask()

        choice = questionary.checkbox(
            message=self.title,
            choices=[Choice(e.name, e, checked=e.pre_selected) for e in self.entries],
            qmark=''
        ).ask()

        if choice is None:
            return None, None, None

        if not self.multi:
            return self.entries[choice]
        else:
            selected: list[MenuEntry] = []
            added: list[MenuEntry] = []
            removed: list[MenuEntry] = []
            for i, entry in enumerate(self.entries):
                if i in choice:
                    selected.append(entry)
                    if not entry.pre_selected:
                        added.append(entry)
                elif entry.pre_selected:
                    removed.append(entry)
            return selected, added, removed


def show_message_menu(message):
    return ActionMenu(message, [MenuEntry('Back')], 'Back').show()
