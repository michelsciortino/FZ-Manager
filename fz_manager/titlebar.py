from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import merge_formatted_text, to_formatted_text
from prompt_toolkit.layout.containers import Container, DynamicContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from fz_manager.factorio_zone_api import FZClient
from fz_manager.utils import Colors


def create_titlebar(client: FZClient = None) -> DynamicContainer:
    def get_content() -> Container:
        app = get_app()
        title = 'Factorio Zone Manager '
        if client and client.server_address:
            server_info = f'Server {client.server_status} at: {client.server_address} '
        else:
            server_info = ' '

        used_width = len(title) + len(server_info)
        total_width = app.output.get_size().columns
        padding_size = total_width - used_width
        padding = to_formatted_text(' ' * padding_size)

        return Window(FormattedTextControl(
            merge_formatted_text(
                to_formatted_text([
                    to_formatted_text(title, 'bold'),
                    padding, server_info
                ])),
            style=f'bg:{Colors.FACTORIO_BG_HEX} fg:{Colors.FACTORIO_FG_HEX}'),
            height=1)

    return DynamicContainer(get_content)
