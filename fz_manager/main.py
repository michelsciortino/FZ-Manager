import asyncio
import json
import os
import re
import zipfile
from os import path, walk

from aioconsole import aprint
from rich.progress import Progress

from fz_manager.factorio_zone_api import FZClient, ServerStatus
from fz_manager.menu import ActionMenu, SelectMenu, CheckboxMenu, MenuEntry, PathMenu, AlertMenu, InputMenu
from fz_manager.shell import Shell
from fz_manager.storage import Storage
from fz_manager.titlebar import create_titlebar
from fz_manager.utils import String, Term, Colors
from fz_manager.utils import run_on_thread


class Main:

    def __init__(self) -> None:
        self.storage = Storage()
        self.client: (FZClient | None) = None
        self.shell: (Shell | None) = None
        self.titlebar = None

    async def main(self):
        token = await self.choose_token()
        if token is None:
            return
        self.client = FZClient(token if not String.isblank(token) else None)
        self.shell = Shell(self.client, self.storage)
        self.titlebar = create_titlebar(self.client)
        asyncio.get_event_loop_policy().get_event_loop().create_task(self.client.connect())
        await self.client.wait_sync()
        self.storage.store('userToken', self.client.user_token)
        if token == '':
            self.storage.token_history.append_string(self.client.user_token)
        await self.main_menu()

    # Main Menu
    async def main_menu(self):
        while True:
            action = await ActionMenu(
                message='Main menu',
                entries=[
                    MenuEntry('Start server', self.start_server, condition=lambda: not self.client.running),
                    MenuEntry('Attach to server', self.attach_to_server, condition=lambda: self.client.running),
                    MenuEntry('Stop server', self.stop_server,
                              condition=lambda: self.client.running and self.client.server_status == ServerStatus.RUNNING),
                    MenuEntry('Manage mods', self.manage_mods_menu, condition=lambda: not self.client.running),
                    MenuEntry('Manage saves', self.manage_saves_menu, condition=lambda: not self.client.running),
                    MenuEntry('Exit')
                ],
                titlebar=self.titlebar,
                clear_screen=True
            ).show()
            Term.cls()
            if action is None or action.name == 'Exit':
                break

    async def manage_mods_menu(self):
        while True:
            action = await ActionMenu(
                message='Manage mods',
                entries=[
                    MenuEntry('Create mod-settings.zip', self.create_mod_settings),
                    MenuEntry('Upload mods', self.upload_mods_menu),
                    MenuEntry('Upload mods using mod-list.json', self.upload_mods_menu_auto)
                    MenuEntry('Enable/Disable uploaded mods', self.disable_mods_menu),
                    MenuEntry('Delete uploaded mods', self.delete_mods_menu),
                    MenuEntry('Back')
                ],
                titlebar=self.titlebar,
                clear_screen=True
            ).show()
            Term.cls()
            if action is None or action.name == 'Back':
                break

    async def manage_saves_menu(self):
        while True:
            action = await ActionMenu(
                message='Main menu',
                entries=[
                    MenuEntry('Upload save', self.upload_save_menu),
                    MenuEntry('Delete save', self.delete_save_menu),
                    MenuEntry('Download save', self.download_save_menu),
                    MenuEntry('Back')
                ],
                titlebar=self.titlebar,
                clear_screen=True
            ).show()
            Term.cls()
            if action is None or action.name == 'Back':
                break

    async def create_mod_settings(self):
        dat = 'mod-settings.dat'

        def validator(p: str) -> bool:
            return path.exists(path.join(p, dat))

        mods_folder_path = await PathMenu(
            'Insert path to mods folder: ',
            only_directories=True,
            validator=validator,
            load_last_value=True,
            titlebar=self.titlebar,
            history=self.storage.mods_path_history
        ).show()
        if mods_folder_path is None:
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
            validator=lambda p: path.exists(p),
            titlebar=self.titlebar,
            load_last_value=True,
            history=self.storage.mods_path_history
        ).show()
        if mods_folder_path is None:
            return

        root, _, filenames = next(walk(mods_folder_path), (None, None, []))
        zip_files = list(filter(lambda n: n.endswith('.zip'), filenames))

        if len(zip_files) == 0:
            return await AlertMenu('No mod found in folder').show()

        selected, _, _ = await CheckboxMenu(
            message='Choose mods to upload',
            entries=[MenuEntry(f, pre_selected=True) for f in zip_files],
        ).show()

        if not selected or not len(selected):
            return

        mods: list[FZClient.Mod] = []
        for entry in selected:
            name = entry.name
            file_path = path.join(root, name)
            size = path.getsize(file_path)
            mods.append(FZClient.Mod(name, file_path, size))

        def callback(monitor):
            progress.update(mod_task, completed=min(monitor.bytes_read, mod.size))

        try:
            with Progress() as progress:
                main_task = progress.add_task('Uploading mods', total=len(mods))
                for mod in mods:
                    mod_task = progress.add_task(f'Uploading {mod.name}', total=mod.size)
                    await self.client.upload_mod(mod, callback)
                    progress.update(main_task, advance=1)

        except BaseException as ex:
            return await AlertMenu(str(ex) or ex.__class__.__name__).show()

    async def upload_mods_menu_auto(self):
        mods_folder_path = await PathMenu(
            'Insert path to mods folder: ',
            only_directories=True,
            validator=lambda p: path.exists(p),
            titlebar=self.titlebar,
            load_last_value=True,
            history=self.storage.mods_path_history
        ).show()
        if mods_folder_path is None:
            return

        root, _, filenames = next(walk(mods_folder_path), (None, None, []))
        zip_files = list(filter(lambda n: n.endswith('.zip'), filenames))

        if len(zip_files) == 0:
            return await AlertMenu('No mod found in folder').show()

        with open(f"{mods_folder_path}/mod-list.json", "r") as f:
            mods = json.load(f)['mods']
            mods.pop(0)

        new_mods = []
        for i in mods:
            if i['enabled']:
                new_mods.append(i)

        zips, i=[], 0
        for zip in zip_files:
            zip = zip.strip('.zip')
            if len(new_mods) == 0:
                break
            if zip == new_mods[i]['name']:
                zips.append(zip)
                if len(new_mods) == 1:
                    break
                i+=1

        mods: list[FZClient.Mod] = []
        for entry in zips:
            name = entry.name
            file_path = path.join(root, name)
            size = path.getsize(file_path)
            mods.append(FZClient.Mod(name, file_path, size))

        def callback(monitor):
            progress.update(mod_task, completed=min(monitor.bytes_read, mod.size))

        try:
            with Progress() as progress:
                main_task = progress.add_task('Uploading mods', total=len(mods))
                for mod in mods:
                    mod_task = progress.add_task(f'Uploading {mod.name}', total=mod.size)
                    await self.client.upload_mod(mod, callback)
                    progress.update(main_task, advance=1)

        except BaseException as ex:
            return await AlertMenu(str(ex) or ex.__class__.__name__).show()

    async def disable_mods_menu(self):
        if not self.client.mods or not len(self.client.mods):
            return await AlertMenu('No uploaded mods found', titlebar=self.titlebar).show()

        _, added, deselected = await CheckboxMenu(
            message='Enable/Disable mods',
            entries=[MenuEntry(m['text'], pre_selected=m['enabled'], ext_index=m['id']) for m in self.client.mods],
            titlebar=self.titlebar
        ).show()
        if added is None or deselected is None:
            return

        with Progress() as progress:
            bar = progress.add_task('Applying changes', total=len(added) + len(deselected))
            for e in added:
                progress.print(f'Enabling {e.name}')
                await self.client.toggle_mod(e.ext_index, True)
                progress.update(bar, advance=1)
            for e in deselected:
                progress.print(f'Disabling {e.name}')
                await self.client.toggle_mod(e.ext_index, False)
                progress.update(bar, advance=1)
            progress.remove_task(bar)

    async def delete_mods_menu(self):
        if not self.client.mods or not len(self.client.mods):
            return await AlertMenu('No uploaded mods found', titlebar=self.titlebar).show()

        selected, _, _ = await CheckboxMenu(
            message='Delete mods',
            entries=[MenuEntry(m['text'], ext_index=m['id']) for m in self.client.mods],
            titlebar=self.titlebar
        ).show()
        with Progress() as progress:
            bar = progress.add_task('Deleting mods', total=len(selected))
            for e in selected:
                progress.print(f'Deleting {e.name}')
                await self.client.delete_mod(e.ext_index)
                progress.update(bar, advance=1)
            progress.remove_task(bar)

    async def upload_save_menu(self):
        file_path = await PathMenu(
            'Insert path to save file: ',
            validator=lambda p: path.exists(p) and path.splitext(p)[1] == '.zip',
            load_last_value=True,
            titlebar=self.titlebar,
            history=self.storage.saves_path_history
        ).show()

        if file_path is None:
            return

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
        if self.client.saves[slot_name] != f'slot {slot.ext_index} (empty)':
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
                await self.client.delete_save_slot(slot_name)

        size = path.getsize(file_path)
        save = FZClient.Save(filename, file_path, size, slot_name)
        with Progress() as progress:
            upload_task = progress.add_task(f'Uploading {filename}', total=size)

            def callback(monitor):
                progress.update(upload_task, completed=min(monitor.bytes_read, size))

            try:
                await self.client.upload_save(save, callback)
                progress.remove_task(upload_task)
            except Exception as ex:
                progress.remove_task(upload_task)
                await AlertMenu(str(ex)).show()

    async def delete_save_menu(self):
        entries = await self.get_remote_slots()
        if len(entries) == 0:
            return await AlertMenu('All the slots are empty', titlebar=self.titlebar).show()

        selected, _, _ = await CheckboxMenu(
            message='Select slots to delete:',
            entries=entries,
            titlebar=self.titlebar
        ).show()

        if not selected:
            return

        with Progress() as progress:
            delete_task = progress.add_task(f'', total=len(selected))
            for slot in selected:
                slot_name = f'slot{slot.ext_index}'
                try:
                    progress.print(f'Deleting slot {slot.ext_index}')
                    await self.client.delete_save_slot(slot_name)
                except Exception as ex:
                    await AlertMenu(str(ex)).show()
                progress.update(delete_task, advance=1)

    async def download_save_menu(self):
        entries = await self.get_remote_slots()
        if len(entries) == 0:
            return await AlertMenu('All the slots are empty', titlebar=self.titlebar).show()

        selected, _, _ = await CheckboxMenu(
            message='Select slots to download:',
            entries=entries,
            titlebar=self.titlebar
        ).show()

        if not selected:
            return

        directory = await PathMenu(
            'Insert download directory path: ',
            only_directories=True,
            load_last_value=True,
            history=self.storage.saves_path_history
        ).show()

        if directory is None:
            return

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
                    await self.client.download_save_slot(slot_name, path.join(directory, f'slot{slot.ext_index}.zip'), update)
                    progress.update(slot_task, completed=expected_size)
                except Exception as ex:
                    progress.print(ex)
                progress.update(download_task, advance=1)

    async def start_server(self):
        if (region := await self.choose_region(show_titlebar=True)) is None:
            return
        if (version := await self.choose_factorio_version()) is None:
            return
        if (slot := await self.choose_slot()) is None:
            return
        await aprint('Starting instance...')
        self.client.add_logs_listener(aprint)
        await run_on_thread(FZClient.start_instance, self.client, region, version, f'slot{slot}')
        while not self.client.running and not self.client.server_address:
            await asyncio.sleep(1)
        self.client.remove_logs_listener(aprint)
        self.storage.persist()

    async def attach_to_server(self):
        await self.shell.show()

    async def stop_server(self):
        await aprint('Stopping instance...')
        self.client.add_logs_listener(aprint)
        await run_on_thread(FZClient.stop_instance, self.client)
        while self.client.running:
            await asyncio.sleep(1)
        self.client.remove_logs_listener(aprint)

    async def get_remote_slots(self):
        slots: list[str] = self.client.saves.values().mapping.values()
        return [MenuEntry(v, ext_index=i + 1) for i, v in enumerate(slots) if not v.endswith('(empty)')]

    # AWS Region
    async def choose_region(self, show_titlebar=False):
        regions = sorted(self.client.regions.items())
        region = self.storage.get('region')

        region = await SelectMenu(
            message='Choose a region:',
            entries=[MenuEntry(f'{r[0]} - {r[1]}', ext_index=r[0]) for r in regions],
            default=region,
            titlebar=self.titlebar if show_titlebar else None
        ).show()
        if region is None:
            return
        self.storage.store('region', region.ext_index)
        return region.ext_index

    # Factorio Version
    # noinspection PyProtectedMember
    async def choose_token(self):
        menu = InputMenu(
            message='Insert userToken:',
            titlebar=create_titlebar(),
            clear_screen=True,
            load_last_value=True,
            history=self.storage.token_history,
        )
        return await menu.show()

    async def choose_factorio_version(self):
        version = self.storage.get('version')
        version = await SelectMenu(
            message='Choose a Factorio version:',
            entries=[MenuEntry(v, ext_index=v) for v in self.client.versions],
            default=version
        ).show()
        if version is None:
            return
        self.storage.store('version', version.ext_index)
        return version.ext_index

    async def choose_slot(self):
        slot = self.storage.get('slot')
        slots: list[str] = self.client.saves.values().mapping.values()
        slot = await SelectMenu(
            message='Select slots to download:',
            entries=[MenuEntry(v, ext_index=i + 1) for i, v in enumerate(slots)],
            default=slot
        ).show()
        if slot is None:
            return None
        self.storage.store('slot', slot.ext_index)
        return slot.ext_index

    def create_header(self):
        if self.client and self.client.server_address:
            run = f'Server running at: {self.client.server_address}'
            status = f'status: {self.client.server_status}'
        else:
            run = ''
            status = ''
        return Term.colorize(Colors.FACTORIO_FG, Colors.FACTORIO_BG,
                             'Factorio Zone Manager', '         ', run, status,
                             end=Term.ENDL + Term.RESET)


def main():
    Term.cls()
    program = Main()
    asyncio.get_event_loop_policy().get_event_loop().run_until_complete(program.main())  # pragma: no cover
    Term.cls()
