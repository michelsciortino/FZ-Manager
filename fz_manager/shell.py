from factorio_zone_api import FZClient
from utils import Term, Colors, String
import asyncio
from aioconsole import aprint
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys

COMMAND_SYMBOL = '>_'


class Shell:

    def __init__(self, client: FZClient):
        self.client = client
        self.attached = False
        self.log_index = 0
        self.cursor = 0
        self.input_command: list[str] = []
        self.commands_history: list[list[str]] = []
        self.back_command: list[str] = []

    async def attach(self):
        Term.cls()
        self.log_index = 0
        self.input_command = []
        self.back_command = []
        for log in self.client.logs:
            await aprint(log, Term.F_RESET)
        await self.print_input_command()
        self.attached = True

        async def on_new_log(new: str) -> None:
            if self.attached:
                await self.print_input_command(Term.HEAD + Term.F_RESET, new, '\n')

        listener = on_new_log
        self.client.add_logs_listener(listener)

        done = asyncio.Event()
        key_input = create_input()

        def keys_ready():
            for key_press in key_input.read_keys():
                try:
                    if key_press.key == key_press.data:
                        self.input_command.append(key_press.data)
                        self.cursor = len(self.commands_history)
                    elif key_press.key == Keys.Enter:
                        command = ''.join(self.input_command).strip()
                        if String.isblank(command):
                            continue
                        print('\r\033[K' + Term.info('COMMAND:', command))
                        self.flush_command()
                    elif key_press.key == Keys.ControlC:
                        done.set()
                        continue
                    elif key_press.key == Keys.ControlH:
                        if len(self.input_command):
                            self.input_command.pop()
                        else:
                            continue
                    elif key_press.key == Keys.Up:
                        if self.cursor > 0:
                            self.cursor -= 1
                            if self.cursor == len(self.commands_history):
                                self.back_command = self.input_command
                            self.input_command = self.commands_history[self.cursor].copy()
                        else:
                            continue
                    elif key_press.key == Keys.Down:
                        if self.cursor < len(self.commands_history) - 1:
                            self.cursor += 1
                            self.input_command = self.commands_history[self.cursor].copy()
                        else:
                            if self.cursor < len(self.commands_history):
                                self.input_command = self.back_command
                            else:
                                continue
                    else:
                        continue
                    asyncio.get_running_loop().create_task(self.print_input_command())
                except Exception as ex:
                    print(ex, end='\n\n')

        with key_input.raw_mode():
            with key_input.attach(keys_ready):
                await done.wait()
        self.client.remove_logs_listener(listener)
        self.attached = False
        Term.cls()

    async def print_input_command(self, *pre: str):
        try:
            await aprint(*pre, Term.HEAD, Term.bg(Colors.FACTORIO_BG), Term.fg(Colors.FACTORIO_FG), Term.ENDL,
                         COMMAND_SYMBOL, ' ', ''.join(self.input_command),
                         sep='', end=Term.RESET)
        except Exception as ex:
            print(ex, end='\n\n')

    def flush_command(self):
        command = ''.join(self.input_command).strip()
        try:
            self.client.send_command(command)
            self.commands_history.append(self.input_command)
            self.cursor = len(self.commands_history)
            self.input_command = []
        except Exception as ex:
            print('Error sending command:', ex)
