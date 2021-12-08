# GTools

## How does this work?

GTools is an automated tool that generates automatically SSDTs (where possible) plus some useful infos of the system itself.

Syntax: `python3 GTools.py`

- `SysReport`: Mandatory argument (unless `--cleanup` is specified) - defines the SysReport folder. (FULL PATH!)
- `-h, --help`: Help page of the script itself.
- `--cleanup`: Cleans up utils/iasl folder and exits.
- `--rebuild-iasl`: Rebuilds iasl module, used for decompiling/recompiling DSDTs/SSDTs.
- `--iasl-bin iasl_binary`: Specifies a different iasl binary to be used for decompiling/recompiling.
- `--skip-ssdtgen`: Skips SSDTs generation.

## Tested on

- macOS Monterey (12.0.1), Python 3.9.9/3.10.0

## Credits

[Apple](https://apple.com) for macOS

[@dreamwhite](https://github.com/dreamwhite) for downloader/logparser modules, as well as mental health support (❤️)

[@CorpNewt](https://github.com/corpnewt/) for [SSDTTime](https://github.com/corpnewt/SSDTTime)

