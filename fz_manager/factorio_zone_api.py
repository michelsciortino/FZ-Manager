from typing import Callable, Coroutine
from websockets import client
import asyncio
import requests
import ssl
import json
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from fz_manager.utils import Term

FACTORIO_ZONE_ENDPOINT = 'factorio.zone'


class FZClient:
    def __init__(self, token: str = None):
        self.socket = None
        self.user_token = token
        self.visit_secret = None
        self.referrer_code = None
        self.regions = {}
        self.versions = {}
        self.slots = {}
        self.saves = {}
        self.mods = []
        self.running = False
        self.launch_id = None
        self.region = None
        self.logs = []
        self.logs_map = {}
        self.logs_listeners: list[Callable[[str], Coroutine]] = []
        self.mods_sync = False
        self.saves_sync = False

    async def connect(self):
        ssl_context = ssl.SSLContext()
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.check_hostname = False
        self.socket = await client.connect(
            f'wss://{FACTORIO_ZONE_ENDPOINT}/ws',
            ping_interval=30,
            ping_timeout=10,
            ssl=ssl_context
        )
        while True:
            message = await self.socket.recv()
            data = json.loads(message)
            match data['type']:
                case 'visit':
                    self.visit_secret = data['secret']
                    self.login()
                case 'options':
                    match data['name']:
                        case 'regions':
                            self.regions = data['options']
                        case 'versions':
                            self.versions = data['options']
                        case 'saves':
                            self.saves = data['options']
                            self.saves_sync = True
                case 'mods':
                    self.mods = data['mods']
                    self.mods_sync = True
                case 'idle':
                    self.running = False
                    self.launch_id = None
                case "starting":
                    self.running = True
                    self.launch_id = data.get('launchId')
                case "stopping":
                    self.running = True
                    self.launch_id = data.get('launchId')
                case 'running':
                    self.running = True
                    self.launch_id = data.get('launchId')
                case 'slot':
                    self.slots[data['slot']] = data
                case 'log':
                    log_id = data['num']
                    if log_id not in self.logs_map:
                        log = data.get('line')
                        self.logs_map[log_id] = log_id
                        self.logs.append(log)
                        await self.on_new_log(log)
                case 'info':
                    log = Term.info('info', data.get('line'))
                    self.logs.append(log)
                    await self.on_new_log(log)
                case 'warn':
                    log = Term.warn('warn', data.get('line'))
                    self.logs.append(log)
                    await self.on_new_log(log)
                case 'error':
                    log = Term.error('error', data.get('line'))
                    self.logs.append(log)
                    await self.on_new_log(log)

    async def wait_sync(self):
        while not self.mods_sync or not self.saves_sync:
            await asyncio.sleep(1)

    def add_logs_listener(self, listener):
        self.logs_listeners.append(listener)

    def remove_logs_listener(self, listener):
        self.logs_listeners.remove(listener)

    async def on_new_log(self, log: str):
        for listener in self.logs_listeners:
            await listener(log)

    # ------ USER APIs ------------------------------------------------------------------
    def login(self):
        resp = requests.post(f'https://{FACTORIO_ZONE_ENDPOINT}/api/user/login',
                             data={
                                 'userToken': self.user_token,
                                 'visitSecret': self.visit_secret,
                                 'reconnected': False
                             })
        if resp.ok:
            body = resp.json()
            self.user_token = body['userToken']
            self.referrer_code = body['referralCode']
        else:
            raise Exception(f'Error logging in: {resp.text}')

    # ------ MODs APIs ------------------------------------------------------------------
    class Mod:
        def __init__(self, name, file_path, size):
            self.name = name
            self.filePath = file_path
            self.size = size

    async def toggle_mod(self, mod_id: int, enabled: bool):
        self.mods_sync = False
        resp = requests.post(f'https://{FACTORIO_ZONE_ENDPOINT}/api/mod/toggle',
                             data={
                                 'visitSecret': self.visit_secret,
                                 'modId': mod_id,
                                 'enabled': enabled
                             })
        if not resp.ok:
            self.mods_sync = True
            raise Exception('Error in toggling mod: {resp.text}')
        await self.wait_sync()

    async def delete_mod(self, mod_id: int):
        self.mods_sync = False
        resp = requests.post(f'https://{FACTORIO_ZONE_ENDPOINT}/api/mod/delete',
                             data={
                                 'visitSecret': self.visit_secret,
                                 'modId': mod_id
                             })
        if not resp.ok:
            self.mods_sync = True
            raise Exception(f'Error in deleting mod: {resp.text}')
        await self.wait_sync()

    async def upload_mod(self, mod: Mod, cb: Callable = None):
        file = open(mod.filePath, 'rb')
        if mod.size > 268435456:  # 256MB
            raise Exception(f'Mod file must be under 256MB')

        encoder = MultipartEncoder({
            'visitSecret': self.visit_secret,
            'file': (mod.name, file, 'application/x-zip-compressed'),
            'size': str(mod.size)
        })
        monitor = MultipartEncoderMonitor(encoder, cb)
        self.mods_sync = False
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/mod/upload',
            headers={'content-type': monitor.content_type},
            data=monitor
        )
        if not resp.ok:
            self.mods_sync = True
            raise Exception(f'Error uploading mod: {resp.text}')
        await self.wait_sync()

    # ------ SAVE APIs ------------------------------------------------------------------
    class Save:
        def __init__(self, name: str, file_path: str, size: int, slot: str):
            self.name = name
            self.filePath = file_path
            self.size = size
            self.slot = slot

    async def delete_save_slot(self, slot: str):
        self.saves_sync = False
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/save/delete', {
                'visitSecret': self.visit_secret,
                'save': slot
            })
        if not resp.ok:
            self.saves_sync = True
            raise Exception(f'Error deleting save: {resp.text}')
        await self.wait_sync()

    async def download_save_slot(self, slot: str, file_path: str, cb: Callable):
        self.saves_sync = False
        with requests.post(
                f'https://{FACTORIO_ZONE_ENDPOINT}/api/save/download',
                data={
                    'visitSecret': self.visit_secret,
                    'save': slot
                },
                stream=True
        ) as response:
            if not response.ok:
                self.saves_sync = True
                raise Exception(f'Error downloading save: {response.text}')
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        cb(file.tell())
                file.close()
        await self.wait_sync()

    async def upload_save(self, save: Save, cb: Callable = None):
        file = open(save.filePath, 'rb')
        if save.size > 100663296:  # 96MB
            raise Exception('Save file must be under 96MB')
        encoder = MultipartEncoder({
            'visitSecret': self.visit_secret,
            'file': (save.name, file, 'application/x-zip-compressed'),
            'size': str(save.size),
            'save': save.slot
        })
        monitor = MultipartEncoderMonitor(encoder, cb)
        self.saves_sync = False
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/save/upload',
            headers={'content-type': monitor.content_type},
            data=monitor
        )
        if not resp.ok:
            self.saves_sync = True
            raise Exception(f'Error uploading save: {resp.text}')
        await self.wait_sync()

    # ------ INSTANCE APIs --------------------------------------------------------------
    def send_command(self, command):
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/instance/console', {
                'visitSecret': self.visit_secret,
                'launchId': self.launch_id,
                'input': command
            })
        if not resp.ok:
            raise Exception(f'Error sending console command: {resp.text}')

    async def start_instance(self, region, version, save):
        print('Starting instance...', end='')
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/instance/start', {
                'visitSecret': self.visit_secret,
                'region': region,
                'version': version,
                'save': save
            })
        if not resp.ok:
            raise Exception(f'Error starting instance: {resp.text}')
        self.launch_id = resp.json()['launchId']
        while not self.running:
            print('.', end='')
            await asyncio.sleep(1)

    async def stop_instance(self):
        print('Stopping instance...', end='')
        resp = requests.post(
            f'https://{FACTORIO_ZONE_ENDPOINT}/api/instance/stop', {
                'visitSecret': self.visit_secret,
                'launchId': self.launch_id,
            })
        if not resp.ok:
            raise Exception(f'Error stopping instance: {resp.text}')
        while self.running:
            print('.', end='')
            await asyncio.sleep(1)
