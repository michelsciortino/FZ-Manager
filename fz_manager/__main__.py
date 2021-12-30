import os
from os import path, walk
import re
import json
import zipfile
import asyncio
from aioconsole import ainput
from rich.progress import Progress

from fz_manager.utils import Colors, String
from menu import ActionMenu, SelectMenu, MenuEntry, PathMenu, AlertMenu
from api.factorio_zone import FZApi
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys


class Main:
    input_command = ''

    def __init__(self) -> None:
        self.api = None

    async def main(self):
        token = await ainput('Insert userToken: ')
        self.api = FZApi(token if not String.isblank(token) else None)
        asyncio.get_event_loop_policy().get_event_loop().create_task(self.api.connect())
        await self.api.wait_sync()
        await self.main_menu()

    # Main Menu
    async def main_menu(self):
        await ActionMenu(
            message='Main menu',
            entries=[
                MenuEntry('Start server', self.start_server, condition=lambda: not self.api.running),
                MenuEntry('Attach to server', self.attach_to_server, condition=lambda: self.api.running),
                MenuEntry('Stop server', self.stop_server, condition=lambda: self.api.running),
                MenuEntry('Manage mods', self.manage_mods_menu),
                MenuEntry('Manage saves', self.manage_saves_menu),
                MenuEntry('Exit')
            ],
            exit_entry=['Exit'],
            clear_screen=True
        ).show()

    async def manage_mods_menu(self):
        await ActionMenu(
            message='Manage mods',
            entries=[
                MenuEntry('Create mod-settings.zip', self.create_mod_settings),
                MenuEntry('Upload mods', self.upload_mods_menu),
                MenuEntry('Enable/Disable uploaded mods', self.disable_mods_menu),
                MenuEntry('Delete uploaded mods', self.delete_mods_menu),
                MenuEntry('Back')
            ],
            exit_entry='Back',
            clear_screen=True
        ).show()

    async def manage_saves_menu(self):
        await ActionMenu(
            message='Main menu',
            entries=[
                MenuEntry('Upload save', self.upload_save_menu),
                MenuEntry('Delete save', self.delete_save_menu),
                MenuEntry('Download save', self.download_save_menu),
                MenuEntry('Back')
            ],
            exit_entry='Back',
            clear_screen=True
        ).show()

    async def create_mod_settings(self):
        dat = 'mod-settings.dat'

        def validator(p: str) -> bool:
            return path.exists(path.join(p, dat))

        mods_folder_path = await PathMenu('Insert path to mods folder: ', only_directories=True, validator=validator).show()
        if not mods_folder_path:
            return

        mod_settings_dat_path = path.join(mods_folder_path, dat)
        info_json_path = path.join(mods_folder_path, 'info.json')
        mod_settings_zip_path = path.join(mods_folder_path, "mod-settings.zip")

        if not path.exists(mod_settings_dat_path):
            return await AlertMenu(f'Unable to find {dat}').show()

        with open(info_json_path, 'w') as fp:
            json.dump({
                'name': dat,
                'version': '0.1.0',
                'title': dat,
                'description': 'Mod settings for factorio.zone created with FZ-Manager tool by @michelsciortino'
            }, fp)

        zf = zipfile.ZipFile(mod_settings_zip_path, "w")
        zf.write(mod_settings_dat_path)
        zf.write(info_json_path)
        zf.close()
        os.remove(info_json_path)
        await AlertMenu(f'{mod_settings_zip_path} created').show()

    async def upload_mods_menu(self):
        mods_folder_path = await PathMenu(
            'Insert path to mods folder: ',
            only_directories=True,
            validator=lambda p: path.exists(p)
        ).show()
        if mods_folder_path is None:
            return

        root, _, filenames = next(walk(mods_folder_path), (None, None, []))
        zip_files = list(filter(lambda n: n.endswith('.zip'), filenames))

        if len(zip_files) == 0:
            await AlertMenu('No mod found in folder').show()
            return

        selected, _, _ = await SelectMenu(
            message='Choose mods to upload',
            entries=[MenuEntry(f, pre_selected=True) for f in zip_files],
            multi_select=True,
            clear_screen=True
        ).show()

        if not selected or not len(selected):
            return

        mods: list[FZApi.Mod] = []
        for entry in selected:
            name = entry.name
            file_path = path.join(root, name)
            size = path.getsize(file_path)
            mods.append(FZApi.Mod(name, file_path, size))

        with Progress() as progress:
            main_task = progress.add_task('Uploading mods', total=len(mods))
            for mod in mods:
                mod_task = progress.add_task(f'Uploading {mod.name}', total=mod.size)

                def callback(monitor):
                    progress.update(mod_task, completed=min(monitor.bytes_read, mod.size))

                try:
                    await self.api.upload_mod(mod, callback)
                except Exception as ex:
                    await AlertMenu(str(ex)).show()
                progress.update(main_task, advance=1)

    async def disable_mods_menu(self):
        if not self.api.mods or not len(self.api.mods):
            return await AlertMenu('No uploaded mods found').show()

        _, added, deselected = await SelectMenu(
            message='Enable/Disable mods',
            entries=[MenuEntry(m['text'], pre_selected=m['enabled'], ext_index=m['id']) for m in self.api.mods],
            multi_select=True,
            clear_screen=True
        ).show()
        if added is None or deselected is None:
            return

        with Progress() as progress:
            bar = progress.add_task('Applying changes', total=len(added) + len(deselected))
            for e in added:
                progress.print(f'Enabling {e.name}')
                await self.api.toggle_mod(e.ext_index, True)
                progress.update(bar, advance=1)
            for e in deselected:
                progress.print(f'Disabling {e.name}')
                await self.api.toggle_mod(e.ext_index, False)
                progress.update(bar, advance=1)
            progress.remove_task(bar)

    async def delete_mods_menu(self):
        if not self.api.mods or not len(self.api.mods):
            return await AlertMenu('No uploaded mods found').show()

        selected, _, _ = await SelectMenu(
            message='Delete mods',
            entries=[MenuEntry(m['text'], ext_index=m['id']) for m in self.api.mods],
            multi_select=True,
            clear_screen=True
        ).show()
        with Progress() as progress:
            bar = progress.add_task('Deleting mods', total=len(selected))
            for e in selected:
                progress.print(f'Deleting {e.name}')
                await self.api.delete_mod(e.ext_index)
                progress.update(bar, advance=1)
            progress.remove_task(bar)

    async def upload_save_menu(self):
        file_path = await PathMenu(
            'Insert path to save file: ',
            validator=lambda p: path.exists(p) and path.splitext(p)[1] == '.zip'
        ).show()

        if not path.exists(file_path):
            return await AlertMenu(f'{file_path} save file does not exist.').show()

        file_extension = path.splitext(file_path)[1]
        filename = path.basename(file_path)
        if file_extension != '.zip':
            return await AlertMenu('Save file must be a zip archive.').show()

        slot = await SelectMenu(
            'Select save slot:',
            [MenuEntry(f'slot {i}', ext_index=i) for i in range(1, 10)]
        ).show()

        if not slot:
            return

        slot_name = f'slot{slot.ext_index}'
        if self.api.saves[slot_name] != f'slot {slot.ext_index} (empty)':
            choice = await SelectMenu(
                f'Slot {slot.ext_index} is already used, do you want to replace it?',
                [
                    MenuEntry('Yes', ext_index=0),
                    MenuEntry('No', ext_index=1)
                ]
            ).show()

            if not choice or choice.ext_index == 1:
                return
            else:
                await self.api.delete_save_slot(slot_name)

        size = path.getsize(file_path)
        save = FZApi.Save(filename, file_path, size, slot_name)
        with Progress() as progress:
            upload_task = progress.add_task(f'Uploading {filename}', total=size)

            def callback(monitor):
                progress.update(upload_task, completed=min(monitor.bytes_read, size))

            try:
                await self.api.upload_save(save, callback)
                progress.remove_task(upload_task)
            except Exception as ex:
                progress.remove_task(upload_task)
                await AlertMenu(str(ex)).show()

    async def delete_save_menu(self):
        slots: list[str] = self.api.saves.values().mapping.values()
        selected, _, _ = await SelectMenu(
            message='Select slots to delete:',
            entries=[MenuEntry(v, ext_index=i + 1) for i, v in enumerate(slots) if not v.endswith('(empty)')],
            clear_screen=True,
            multi_select=True
        ).show()
        if not selected:
            return

        with Progress() as progress:
            delete_task = progress.add_task(f'', total=len(selected))
            for slot in selected:
                slot_name = f'slot{slot.ext_index}'
                try:
                    progress.print(f'Deleting slot {slot.ext_index}')
                    await self.api.delete_save_slot(slot_name)
                except Exception as ex:
                    await AlertMenu(str(ex)).show()
                progress.update(delete_task, advance=1)

    async def download_save_menu(self):
        slots: list[str] = self.api.saves.values().mapping.values()
        selected, _, _ = await SelectMenu(
            message='Select slots to download:',
            entries=[MenuEntry(v, ext_index=i + 1) for i, v in enumerate(slots) if not v.endswith('(empty)')],
            clear_screen=True,
            multi_select=True
        ).show()
        if not selected:
            return

        directory = await PathMenu('Insert download directory path: ', only_directories=True).show()
        if not path.exists(directory):
            return await AlertMenu('Directory not found').show()
        if not path.isdir(directory):
            return await AlertMenu(f'{directory} is not a directory').show()

        with Progress() as progress:
            download_task = progress.add_task(f'Downloading slots', total=len(selected))
            for slot in selected:
                expected_size = float(re.search('(\d+.\d+)MB', slot.name)[1]) * 1048576
                slot_task = progress.add_task(f'Slot {slot.ext_index}', total=expected_size)

                def update(n_bytes):
                    progress.update(slot_task, completed=n_bytes)

                slot_name = f'slot{slot.ext_index}'
                try:
                    await self.api.download_save_slot(slot_name, path.join(directory, f'slot{slot.ext_index}.zip'), update)
                    progress.update(slot_task, completed=expected_size)
                except Exception as ex:
                    progress.print(ex)
                progress.update(download_task, advance=1)

    async def start_server(self):
        if not (region := await self.choose_region()):
            return
        if not (version := await self.choose_factorio_version()):
            return

        slots: list[str] = self.api.saves.values().mapping.values()
        slot = await SelectMenu(
            message='Select slots to download:',
            entries=[MenuEntry(v, ext_index=i + 1) for i, v in enumerate(slots)]
        ).show()
        if not slot:
            return
        await self.api.start_instance(region, version, f'slot{slot.ext_index}')

    async def attach_to_server(self):
        await self.api.attach_to_socket()

        done = asyncio.Event()
        key_input = create_input()

        def keys_ready():
            for key_press in key_input.read_keys():
                if key_press.key == Keys.Enter:
                    print('\r\033[K' + Colors.info('COMMAND:', self.api.input_command))
                    self.api.flush_command()
                elif key_press.key == Keys.ControlC:
                    done.set()
                    continue
                else:
                    self.api.input_command += key_press.data
                self.api.print_input_command()

        with key_input.raw_mode():
            with key_input.attach(keys_ready):
                await done.wait()
        self.api.detach_from_socket()

    async def stop_server(self):
        await self.api.stop_instance()

    # AWS Region
    async def choose_region(self):
        regions = sorted(self.api.regions.items())
        region = await SelectMenu(
            message='Choose a region:',
            entries=[MenuEntry(f'{r[0]} - {r[1]}', ext_index=r[0]) for r in regions],
        ).show()
        return region.ext_index if region else None

    # Factorio Version
    async def choose_factorio_version(self):
        version = await SelectMenu(
            message='Choose a Factorio version:',
            entries=[MenuEntry(v) for v in self.api.versions],
        ).show()
        return version.name if version else None


if __name__ == '__main__':
    program = Main()
    # noinspection PyBroadException
    try:
        asyncio.get_event_loop_policy().get_event_loop().run_until_complete(program.main())  # pragma: no cover
    except:
        pass
