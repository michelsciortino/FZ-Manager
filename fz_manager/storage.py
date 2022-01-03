import os
from os import path, umask
import tempfile
import json

from prompt_toolkit.history import FileHistory


class Storage:
    def __init__(self):
        self.temp_dir_path = path.join(tempfile.gettempdir(), '.fzm')
        if path.exists(self.temp_dir_path):
            if not path.isdir(self.temp_dir_path):
                raise RuntimeError(f'{self.temp_dir_path} path is occupied')
        else:
            os.mkdir(self.temp_dir_path)

        self.store_path = path.join(self.temp_dir_path, '.fzm_store')
        self.command_history_path = path.join(self.temp_dir_path, '.fzm_command_history')
        self.token_history_path = path.join(self.temp_dir_path, '.fzm_token_history')
        self.mods_path_history_path = path.join(self.temp_dir_path, '.fzm_mods_path_history')
        self.saves_path_history_path = path.join(self.temp_dir_path, '.fzm_saves_path_history')

        self.command_history = FileHistory(self.command_history_path)
        self.token_history = FileHistory(self.token_history_path)
        self.mods_path_history = FileHistory(self.mods_path_history_path)
        self.saves_path_history = FileHistory(self.saves_path_history_path)
        self.in_mem_store: dict[str, (str | int)] | None = None
        self.load()

    def store(self, key: str, value: (str | int)):
        self.in_mem_store[key] = value

    def get(self, key: str) -> (str | int | None):
        return self.in_mem_store.get(key)

    def persist(self) -> None:
        pre_umask = umask(77)
        try:
            with open(self.store_path, 'w') as fp:
                json.dump(self.in_mem_store, fp)
        finally:
            umask(pre_umask)

    def load(self) -> None:
        if path.exists(self.store_path) and path.isfile(self.store_path):
            try:
                with open(self.store_path, 'r') as fp:
                    self.in_mem_store = dict()
                    self.in_mem_store.update(json.load(fp))
            except IOError as e:
                print(e)
        else:
            self.in_mem_store = dict()
