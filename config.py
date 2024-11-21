import os
import json

__all__ = ["config"]

config = {}
### check if conf has WLAN detains
if "config.json" in os.listdir():
    with open("config.json") as f:
        while jsonline := f.readline():
            cfg = json.loads(jsonline.strip())
            config.update(cfg)
    print(json.dumps(config))
else:
    print("==> config.json not found !")


def saveconfig(configdict):
    with open("config.json") as g:
        for key, val in configdict.items():
            g.write(json.dumps({key: val}))
