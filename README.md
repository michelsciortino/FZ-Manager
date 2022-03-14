# FZ-Manager
FactorioZone Manager is a command line tool made to manage an instance of Factorio Server deployed on AWS via [Factorio Zone](https://factorio.zone/).
It implements all the features of factorio.zone site plus some aggregated ones to upload all the mods sequentially with just one command.

## Features

- Start a new Server, choosing an AWS Region, a Factorio version and a saveslot
- Attach to a running Server, sending command directly to its terminal interface
- Upload multiple mods from your filesystem at a once
- Generate the mod-setting.zip archive (upload it as a mod)
- Delete multiple mods at a once
- Manage your remote saves

## Requirements
I order to install this tool, you need `python 3.10` installed, alongside with `pip`

## Installation
```sh
pip install fz-manager
```

## Usage
```sh
fz-manager
```
or just `fzm`
