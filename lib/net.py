__all__ = ["setup"]

import network, time, os
from machine import Pin

led = Pin("LED", Pin.OUT)
wlan = network.WLAN(network.STA_IF)


def __init():
    led.toggle()
    wlan.active(True)
    time.sleep(2)
    led.toggle()
    return wlan


def __scan(search=""):
    led.toggle()
    ssids = wlan.scan()
    time.sleep(2)
    led.toggle()
    if search == "":
        pass
    else:
        ssids = list(filter(lambda s: search in s[0], ssids))
    if search in ssids:
        return [search]  # return exact match
    else:
        return ssids  # else all matches


def __connect(ssid, password):
    led.toggle()
    force = True if ssid != "" else False
    if force:
        ssid = __scan(ssid)
        if len(ssid):
            ssid = ssid[0][0]
            wlan.connect(ssid, password)
            while not wlan.isconnected():
                pass
    led.toggle()
    return ssid, wlan.ifconfig()


def setup(ssid, password=""):
    __init()
    ssid, ifconfig = __connect(ssid, password)
    return ssid, ifconfig[0]


### check if conf has WLAN details
from config import config

if "WLAN" in config:
    if not wlan.isconnected():
        print(f"Found config, attempting ssid = {config['WLAN']['ssid']}")
        status = setup(config["WLAN"]["ssid"], config["WLAN"]["pass"])
        print(status)
    else:
        print("Already connected with IP:", wlan.ifconfig()[0])
