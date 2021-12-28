from typing import Callable
from simple_term_menu import TerminalMenu

class MenuEntry():
    def __init__(self, name: str, callback: Callable = None, pre_selected: bool = False, ext_index : (int|str) = None):
        self.name = name
        self.callback = callback
        self.pre_selected = pre_selected
        self.ext_index = ext_index

class ActionMenu():
    def __init__(self, title: str, entries: list[MenuEntry], exit: str|list[str] = None, clear_screen: bool = False):
        self.title = title
        self.entries = entries
        self.cls = clear_screen
        self.ext = exit

    def show(self) -> None:
        while True:
            menu = TerminalMenu(
                [e.name for e in self.entries],
                clear_screen=self.cls,
                title=self.title
            )
            choice = menu.show()
            if choice is None:
                return

            entry = self.entries[choice]
            entry.callback and entry.callback()
            
            if self.ext is str and self.ext==entry.name:
                break
            if self.ext is list and entry.name in self.ext:
                break

class SelectMenu():
    def __init__(self, title: str, entries: list[MenuEntry], clear_screen: bool = False, multi_select: bool = False):
        self.title = title
        self.entries = entries
        self.multi = multi_select
        self.cls = clear_screen

    def show(self) -> (MenuEntry | tuple[list[MenuEntry], list[MenuEntry], list[MenuEntry]]):
        preselected = [i for i,e in enumerate(self.entries) if e.pre_selected]
        menu = TerminalMenu(
            [e.name for e in self.entries],
            preselected_entries=preselected,
            clear_screen=self.cls,
            title=self.title,
            multi_select=self.multi,
            multi_select_select_on_accept=False
        )
        choice = menu.show()
        if choice is None:
            return (None,None,None)
        
        if not self.multi:
            return self.entries[choice]
        else:
            selected : list[MenuEntry]= []
            added: list[MenuEntry] = []
            removed: list[MenuEntry] = []
            for i, entry in enumerate(self.entries):
                if i in choice:
                    selected.append(entry)
                    if not entry.pre_selected:
                        added.append(entry)
                elif entry.pre_selected:
                    removed.append(entry)
            return (selected,added,removed)