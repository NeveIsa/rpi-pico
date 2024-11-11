import os

__all__ = ["config"]

config = {}
### check if conf has WLAN detains
if "config.json" in os.listdir():
    import json

    with open("config.json") as f:
        while jsonline := f.readline():
            cfg = json.loads(jsonline.strip())
            config.update(cfg)
    print(json.dumps(config))
else:
    print("==> config.json not found !")
