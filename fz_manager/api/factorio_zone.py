from typing import Callable
from websockets import client
import requests
import json
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

FACTORIO_ZONE_ENDPOINT = 'factorio.zone'

class FZApi:
    def __init__(self, token: str):
        self.userToken = token
        self.visitSecret = None
        self.launchId = None
        self.socket = None
        self.running = False
        self.regions = {}
        self.versions = {}
        self.slots = {}
        self.saves = {}
        self.mods = []
        self.input_command = ''

    async def sync(self):
        async with self.connect() as socket:
            self.running=False
            self.launchId=None
            self.socket=None
            while True:
                message = await socket.recv()
                data = json.loads(message)
                match data['type']:
                    case 'visit':
                        self.visitSecret = data['secret']
                        self.login()
                    case 'options':
                        match data['name']:
                            case 'regions':
                                self.regions=data['options']
                            case 'versions':
                                self.versions=data['options']
                            case 'saves':
                                self.saves=data['options']
                    case 'mods':
                        self.mods=data['mods']
                    case 'info':
                        if data.get('line') == 'ready':
                            await socket.close()
                            break
                    case 'running':           
                        self.running=True
                        self.launchId=data.get('launchId')
                        self.socket=data.get('socket')
                        await socket.close()
                        break
                    case 'log':
                        print(data.get('line'))
    
    async def attach_to_socket(self):
        async with self.connect() as socket:
            self.running=False
            self.launchId=None
            self.socket=None
            lineNum=0
            while True:
                message = await socket.recv()
                data = json.loads(message)
                match data['type']:
                    case 'visit':
                        self.visitSecret = data['secret']
                        self.login()
                    case 'running':           
                        self.running=True
                        self.launchId=data.get('launchId')
                        self.socket=data.get('socket')
                    case 'log':
                        n = data.get('num')
                        if n is not None and n > lineNum:
                            print(f'\r\033[K{data.get("line")}')
                            self.print_input_command()
                            lineNum=n

    def print_input_command(self):
        print(f'\r\033[K> {self.input_command}',end='')

    def connect(self):
        return client.connect(
            f'wss://{FACTORIO_ZONE_ENDPOINT}/ws',
            ping_interval=30,
            ping_timeout=10
        )

#------ USER APIs ------------------------------------------------------------------
    def login(self):
        resp = requests.post(f'https://{FACTORIO_ZONE_ENDPOINT}/api/user/login',
                             data={
                                 'userToken': self.userToken,
                                 'visitSecret': self.visitSecret,
                                 'reconnected': False
                             })
        if resp.ok:
            body = resp.json()
            self.userToken = body['userToken']
            self.referrerCode = body['referralCode']
        else:
            raise Exception(f'Error logging in: {resp.text}')

#------ MODs APIs ------------------------------------------------------------------
    class Mod():
        def __init__(self, name,filePath,size):
            self.name = name
            self.filePath = filePath
            self.size=  size

    def toggle_mod(self, modId:int, enabled:bool):
        resp = requests.post(f'https://{FACTORIO_ZONE_ENDPOINT}/api/mod/toggle',
                             data={
                                 'visitSecret': self.visitSecret,
                                 'modId': modId,
                                 'enabled': enabled
                             })
        if not resp.ok:
            raise Exception('Error in toggling mod: {resp.text}')

    def delete_mod(self, modId:int):
        resp = requests.post(f'https://{FACTORIO_ZONE_ENDPOINT}/api/mod/delete',
                             data={
                                 'visitSecret': self.visitSecret,
                                 'modId': modId
                             })
        if not resp.ok:
            raise Exception(f'Error in deleting mod: {resp.text}')

    def upload_mod(self, mod: Mod, cb : Callable = None):
        file = open(mod.filePath,'rb')
        if mod.size > 268435456: #256MB
            raise Exception(f'Mod file must be under 256MB')

        encoder = MultipartEncoder({
                'visitSecret': self.visitSecret,
                'file': (mod.name, file, 'application/x-zip-compressed'),
                'size': str(mod.size)
            })
        monitor = MultipartEncoderMonitor(encoder, cb)
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/mod/upload',
            headers={ 'content-type' : monitor.content_type },
            data=monitor
        )
        if not resp.ok:
            raise Exception(f'Error uploading mod: {resp.text}')

#------ SAVE APIs ------------------------------------------------------------------
    class Save():
        def __init__(self, name:str, filePath:str, size:int, slot:str):
            self.name=name
            self.filePath=filePath
            self.size=size
            self.slot=slot
    
    def delete_save_slot(self, slot: str):
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/save/delete',{
            'visitSecret': self.visitSecret,
            'save': slot
        })
        if not resp.ok:
            raise Exception(f'Error deleting save: {resp.text}')

    def download_save_slot(self, slot: str, filePath: str, cb: Callable) -> bytes:
        with requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/save/download',
            data={
                'visitSecret': self.visitSecret,
                'save': slot
            },
            stream=True
        ) as response:
            if not response.ok:
                raise Exception(f'Error downloading save: {response.text}')
            with open(filePath, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192): 
                    if chunk:
                        file.write(chunk)
                        cb(file.tell())
                file.close()
    

    def upload_save(self,save: Save, cb : Callable = None):
        file = open(save.filePath,'rb')
        
        if save.size > 100663296: #96MB
            raise Exception('Save file must be under 96MB')
        encoder = MultipartEncoder({
                'visitSecret': self.visitSecret,
                'file': (save.name, file, 'application/x-zip-compressed'),
                'size': str(save.size),
                'save': save.slot
            })
        monitor = MultipartEncoderMonitor(encoder, cb)
        
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/save/upload',
            headers={ 'content-type' : monitor.content_type },
            data=monitor
        )
        if not resp.ok:
            raise Exception(f'Error uploading save: {resp.text}')

#------ INSTANCE APIs --------------------------------------------------------------
    def flush_command(self):               
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/instance/console', {
                'visitSecret': self.visitSecret,
                'launchId': self.launchId,
                'input': self.input_command
            })
        if not resp.ok:
            raise Exception(f'Error sending console command: {resp.text}')
        self.input_command=''

    def start_instance(self, region, version, save):
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/instance/start',{
            'visitSecret': self.visitSecret,
            'region': region,
            'version': version,
            'save': save
        })
        if not resp.ok:
           raise Exception(f'Error starting instance: {resp.text}')
        return resp.json()['launchId']

    def stop_instance(self, launchId):
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/instance/start',{
            'visitSecret': self.visitSecret,
            'launchId': launchId
        })
        if not resp.ok:
            raise Exception(f'Error stopping instance: {resp.text}')