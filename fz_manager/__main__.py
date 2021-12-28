import os
from os import path, sync, walk
import re
import json
import zipfile
import asyncio
from rich.progress import Progress
from menu import ActionMenu, SelectMenu, MenuEntry
from api.factorio_zone import FZApi
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys

class Main():
    input_command = ''
    
    def __init__(self) -> None:
        self.userToken = 'sjjaYBT2uavSwA4gZoCoJPXe'# input('Insert userToken: ')
        self.api = FZApi(self.userToken)
        self.socketTask = None
    
    def main(self):
        self.sync()
        if not self.api.running:
            self.main_menu()
        else:
            asyncio.get_event_loop_policy().get_event_loop().run_until_complete(self.on_server_running())
    
    def sync(self):
        print('Synchronizing...')
        asyncio.get_event_loop_policy().get_event_loop().run_until_complete(self.api.sync())
        
    #Main Menu
    def main_menu(self):
        ActionMenu(
            title='Main menu',
            entries=[
                MenuEntry('Start server', self.start_server),
                MenuEntry('Manage mods', self.manage_mods_menu),
                MenuEntry('Manage saves', self.manage_saves_menu),
                MenuEntry('Exit')
            ],
            exit=['Start server','Exit'],
            clear_screen=True
        ).show()

    def manage_mods_menu(self):
        ActionMenu(
            title='Manage mods',
            entries=[
                MenuEntry('Create mod-settings.zip', self.create_mod_settings),
                MenuEntry('Upload mods', self.upload_mods_menu),
                MenuEntry('Enable/Disable uploaded mods', self.disable_mods_menu),
                MenuEntry('Delete uploaded mods', self.delete_mods_menu),
                MenuEntry('Back')
            ],
            exit='Back',
            clear_screen= True
        ).show()
    
    def manage_saves_menu(self):
        ActionMenu(
            title='Main menu',
            entries=[
                MenuEntry('Upload save', self.upload_save_menu),
                MenuEntry('Delete save', self.delete_save_menu),
                MenuEntry('Download save', self.download_save_menu),
                MenuEntry('Back')
            ],
            exit='Back',
            clear_screen=True
        ).show()
            
    def create_mod_settings(self):
        dat='mod-settings.dat'
        modsFolderPath = input('Insert path to mods folder: ')
        modSettingsDatPath = path.join(modsFolderPath,dat)
        infoJsonPath = path.join(modsFolderPath,'info.json')
        modSettingsZipPath = path.join(modsFolderPath,"mod-settings.zip")
        
        if not path.exists(modSettingsDatPath):
            return self.show_message_menu(f'Unable to find {dat}')
        
        with open(infoJsonPath, 'w') as fp:
            json.dump({
                'name': dat,
                'version': '0.1.0',
                'title': dat,
                'description': 'Mod settings for factorio.zone created with FZ-Manager tool by @michelsciortino'
            }, fp)
        
        zf = zipfile.ZipFile(modSettingsZipPath, "w")
        zf.write(modSettingsDatPath)
        zf.write(infoJsonPath)
        zf.close()
        os.remove(infoJsonPath)
        self.show_message_menu(f'{modSettingsZipPath} created')

    def upload_mods_menu(self):
        modsFolderPath = input('Insert path to mods folder: ')
        
        root,_,filenames = next(walk(modsFolderPath), (None, None, []))
        zipFiles = list(filter(lambda name: name.endswith('.zip'),filenames))
        
        if len(zipFiles) == 0:
            print('No mod found in folder')
            return
        
        selected, _, _ = SelectMenu(
            title='Choose mods to upload',
            entries=[MenuEntry(f,pre_selected=True) for f in zipFiles],
            multi_select=True,
            clear_screen=True
        ).show()
        
        if not selected or not len(selected):
            return
        
        mods: list[FZApi.Mod]=[]
        for entry in selected:
            name = entry.name
            filePath = path.join(root,name)
            size = path.getsize(filePath)
            mods.append(FZApi.Mod(name,filePath,size))
        
        with Progress() as progress:
            mainTask = progress.add_task('Uploading mods', total=len(mods))
            for mod in mods:
                modTask = progress.add_task(f'Uploading {mod.name}', total=mod.size)
                def callback(monitor):
                    progress.update(modTask, completed=min(monitor.bytes_read,mod.size))
                try:
                    self.api.upload_mod(mod, callback)
                except Exception as ex:
                    self.show_message_menu(str(ex))
                progress.update(mainTask, advance=1)
        self.sync()
 
    def disable_mods_menu(self):
        _, added, deselected = SelectMenu(
            title='Enable/Disable mods',
            entries=[MenuEntry(m['text'],pre_selected=m['enabled'], ext_index=m['id']) for m in self.api.mods],
            multi_select=True,
            clear_screen=True
        ).show()
        if added is None or deselected is None:
            return
        
        with Progress() as progress:
            bar=progress.add_task('Applying changes',total=len(added)+len(deselected))
            for e in added:
                progress.print(f'Enabling {e.name}')
                self.api.toggle_mod(e.ext_index,True)
                progress.update(bar,advance=1)
            for e in deselected:
                progress.print(f'Disabling {e.name}')
                self.api.toggle_mod(e.ext_index,False)
                progress.update(bar,advance=1)
            progress.remove_task(bar)
        self.sync()
    
    def delete_mods_menu(self):
        if not self.api.mods or not len(self.api.mods):
            return self.show_message_menu()

        selected, _, _ = SelectMenu(
            title='Delete mods',
            entries=[MenuEntry(m['text'], ext_index=m['id']) for m in self.api.mods],
            multi_select=True,
            clear_screen=True
        ).show()
        with Progress() as progress:
            bar=progress.add_task('Deleting mods',total=len(selected))
            for e in selected:
                progress.print(f'Deleting {e.name}')
                self.api.delete_mod(e.ext_index)
                progress.update(bar,advance=1)
            progress.remove_task(bar)
        self.sync()

    def upload_save_menu(self):
        filePath = input('Insert path to save file: ')
        
        if not path.exists(filePath):
            return self.show_message_menu(f'{filePath} save file does not exist.')
        
        file_extension = path.splitext(filePath)[1]
        filename = path.basename(filePath)
        if file_extension != '.zip':
            return self.show_message_menu('Save file must be a zip archive.')
        
        slot = SelectMenu(
            'Select save slot:',
            [ MenuEntry(f'slot {i}',ext_index=i) for i in range(1,10)]
        ).show()
        
        if not slot:
            return
        
        slotName=f'slot{slot.ext_index}'
        if self.api.saves[slotName] != f'slot {slot.ext_index} (empty)':
            choice = SelectMenu(
                f'Slot {slot.ext_index} is already used, do you want to replace it?',
                [
                    MenuEntry('Yes', ext_index=0),
                    MenuEntry('No', ext_index=1)
                ]
            ).show()
            
            if not choice or choice.ext_index==1:
                return
            else:
                self.api.delete_save_slot(slotName)
        
        size = path.getsize(filePath)
        save = FZApi.Save(filename,filePath,size,slotName)
        with Progress() as progress:
            uploadTask = progress.add_task(f'Uploading {filename}', total=size)
            def callback(monitor):
                        progress.update(uploadTask, completed=min(monitor.bytes_read,size))
            try:         
                self.api.upload_save(save,callback)
                progress.remove_task(uploadTask)
            except Exception as ex:
                progress.remove_task(uploadTask)
                self.show_message_menu(str(ex))
        self.sync()
    
    def delete_save_menu(self):
        slots: list[str] = self.api.saves.values().mapping.values()
        selected,_,_ = SelectMenu(
            title='Select slots to delete:',
            entries=[MenuEntry(v,ext_index=i+1) for i,v in enumerate(slots) if not v.endswith('(empty)')],
            clear_screen=True,
            multi_select=True
        ).show()
        if not selected:
            return
        
        with Progress() as progress:
            deleteTask = progress.add_task(f'', total=len(selected))
            for slot in selected:
                slotName=f'slot{slot.ext_index}'
                try:
                    progress.print(f'Deleting slot {slot.ext_index}')
                    self.api.delete_save_slot(slotName)
                except Exception as ex:
                    self.show_message_menu(str(ex))
                progress.update(deleteTask,advance=1)
        self.sync()

    def download_save_menu(self):
        slots: list[str] = self.api.saves.values().mapping.values()
        selected,_,_ = SelectMenu(
            title='Select slots to download:',
            entries=[MenuEntry(v,ext_index=i+1) for i,v in enumerate(slots) if not v.endswith('(empty)')],
            clear_screen=True,
            multi_select=True
        ).show()
        if not selected:
            return
        
        directory = input('Insert download directory path: ')
        if not path.exists(directory):
            return self.show_message_menu('Directory not found')
        if not path.isdir(directory):
            return self.show_message_menu(f'{directory} is not a directory')
        
        with Progress() as progress:
            downloadTask = progress.add_task(f'Downloading slots', total=len(selected))
            for slot in selected:
                expectedSize= float(re.search('(\d+.\d+)MB',slot.name)[1])*1048576
                slotTask = progress.add_task(f'Slot {slot.ext_index}', total=expectedSize)
                def update(bytes):
                    progress.update(slotTask, completed=bytes)
                slotName=f'slot{slot.ext_index}'
                try:
                    self.api.download_save_slot(slotName, path.join(directory, f'slot{slot.ext_index}.zip'), update)
                    progress.update(slotTask, completed=expectedSize)
                except Exception as ex:
                    progress.print(ex)
                progress.update(downloadTask,advance=1)
        self.sync()
        
    def start_server(self):
        if not (region:=self.choose_region()):
            return
        if not (version:=self.choose_factorio_version()):
            return
        
        slots: list[str] = self.api.saves.values().mapping.values()
        slot = SelectMenu(
            title='Select slots to download:',
            entries=[MenuEntry(v,ext_index=i+1) for i,v in enumerate(slots)]
        ).show()
        if not slot:
            return
        self.api.start_instance(region,version,f'slot{slot.ext_index}')
        self.sync()
    
    async def on_server_running(self):
        asyncio.get_event_loop().create_task(self.api.attach_to_socket())
        
        done = asyncio.Event()
        input = create_input()
        
        def keys_ready():
            for key_press in input.read_keys():
                if key_press.key == Keys.Enter:
                    print('\r\033[KCOMMAND:',self.api.input_command)
                    self.api.flush_command()
                elif key_press.key == Keys.ControlC:
                    done.set()
                    continue
                else:
                    self.api.input_command+=key_press.data
                self.api.print_input_command()
                    
        with input.raw_mode():
            with input.attach(keys_ready):
                await done.wait()
        
        

    def show_message_menu(self, message):
        ActionMenu(message,[MenuEntry('Back')],'Back').show()

    #AWS Region
    def choose_region(self):
        regions = sorted(self.api.regions.items())
        region = SelectMenu(
            title='Choose a region:',
            entries=[MenuEntry(f'{r[0]} - {r[1]}', ext_index=r[0]) for r in regions],
        ).show()
        return region.ext_index if region else None

    #Factorio Version
    def choose_factorio_version(self):
        version = SelectMenu(
            title='Choose a Factorio version:',
            entries=[MenuEntry(v) for v in self.api.versions],
        ).show()
        return version.name if version else None

if __name__ == '__main__':
    program = Main()
    program.main()  # pragma: no cover