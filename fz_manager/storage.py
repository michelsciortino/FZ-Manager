from os import path, umask
import tempfile
import json

TEMP_DIR = tempfile.gettempdir()
STORE_PATH = path.join(TEMP_DIR, '.fzm_store')
__in_mem: dict[str, (str | int)] = dict()


def store(key: str, value: (str | int)):
    __in_mem[key] = value


def get(key: str) -> (str | int | None):
    return __in_mem.get(key)


def persist() -> None:
    pre_umask = umask(77)
    try:
        with open(STORE_PATH, 'w') as fp:
            json.dump(__in_mem, fp)
    except IOError as e:
        print(e)
    finally:
        umask(pre_umask)


def read() -> None:
    if path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, 'r') as fp:
                __in_mem.clear()
                __in_mem.update(json.load(fp))
        except IOError as e:
            print(e)
    else:
        __in_mem.clear()
