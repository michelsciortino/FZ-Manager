from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import fragment_list_to_text, to_formatted_text, ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window, HSplit, VSplit
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl as FtC
from prompt_toolkit.layout.processors import Processor, Transformation, TransformationInput
from prompt_toolkit.output import ColorDepth

from fz_manager.factorio_zone_api import FZClient
from fz_manager.storage import Storage
from fz_manager.titlebar import create_titlebar
from fz_manager.utils import Colors, Term, run_on_thread

COMMAND_SYMBOL = '>_'


class FormatText(Processor):
    def apply_transformation(self, ti: TransformationInput):
        fragments = to_formatted_text(ANSI(fragment_list_to_text(ti.fragments)))
        return Transformation(fragments)


class Shell:
    def __init__(self, client: FZClient, storage: Storage):
        self.client = client
        self.commands_history = storage.command_history
        self.logs_buffer = Buffer()
        self.command_buffer = Buffer(history=self.commands_history)
        self.app: Application | None = None

        command_kb = KeyBindings()

        @command_kb.add(Keys.Enter)
        async def submit_command(_):
            command = self.command_buffer.text.strip()
            if not command:
                return
            self.push_log(Term.info('COMMAND:', command))
            try:
                self.command_buffer.reset(append_to_history=True)
                await run_on_thread(FZClient.send_command, self.client, command)
            except Exception as ex:
                self.push_log(Term.error('Error:', str(ex)))

        @command_kb.add(Keys.Up)
        def suggest_up(_):
            self.command_buffer.history_backward()

        @command_kb.add(Keys.Down)
        def suggest_down(_):
            self.command_buffer.history_forward()

        command_window = Window(
            BufferControl(self.command_buffer,
                          key_bindings=command_kb,
                          focusable=True,
                          focus_on_click=True)
        )
        self.layout = Layout(HSplit([
            create_titlebar(client),
            Window(BufferControl(self.logs_buffer,
                                 focusable=False,
                                 input_processors=[FormatText()]), wrap_lines=False, style='bg:#212121'),
            VSplit([
                Window(FtC(COMMAND_SYMBOL), width=len(COMMAND_SYMBOL) + 1, style=f'fg:{Colors.FACTORIO_FG_HEX} bold'),
                command_window
            ], height=1, style=f'bg:{Colors.FACTORIO_BG_HEX}')
        ]), focused_element=command_window)

        self.client.add_logs_listener(self.push_log)

    def push_log(self, *log: str) -> None:
        if not log or len(log) == 0:
            return
        text = ' '.join(log)
        if self.logs_buffer.text:
            self.logs_buffer.text += '\n' + text
        else:
            self.logs_buffer.text += text
        self.logs_buffer.cursor_down(self.logs_buffer.document.line_count - self.logs_buffer.document.cursor_position_row)

    async def show(self) -> None:
        app_kb = KeyBindings()

        @app_kb.add(Keys.ControlC)
        def __exit(_):
            self.app.exit()

        self.app = Application(layout=self.layout,
                               full_screen=True,
                               color_depth=ColorDepth.DEPTH_24_BIT,
                               refresh_interval=1,
                               mouse_support=True,
                               erase_when_done=True,
                               key_bindings=app_kb
                               )
        await self.app.run_async()
