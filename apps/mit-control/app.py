import json, os
from machine import Pin, PWM, ADC, I2C
from ssd1306 import SSD1306_I2C
import conf
from udprpc import RPC
from time import sleep_ms, time
import net


class Device:
    def __init__(self, motpin, potpin, btnpin, buzpin):
        self.motor = PWM(Pin(motpin), freq=20000)
        self.pot = ADC(Pin(potpin))
        self.motorduty = 0
        self.btnpin = Pin(btnpin, Pin.IN, Pin.PULL_UP)
        self.buzpin = Pin(buzpin, Pin.OUT)

    def setpwm(self, val):
        self.motorduty = val
        return self.motor.duty_u16(val)

    def getadc(self):
        return self.pot.read_u16() // 2**6

    def readbtn(self):
        btn = self.btnpin.value()
        if btn:  # not pressed
            return btn  # return immediately
        else:  # pressed
            self.buzz(75)  # buzz + debounce for 75ms
            while not self.btnpin.value():
                pass  # wait untill released
            self.buzz(50)  # buzz + debounce
            return btn

    def buzz(self, beepms=100):
        """beepms is millisecs to beep"""
        self.buzpin.on()
        sleep_ms(beepms)
        self.buzpin.off()


######## INIT DEVICE ########
dev = Device(conf.MOTPIN, conf.POTPIN, conf.BTNPIN, conf.BUZPIN)


######## NETWORK ########
ssid, ifconfig = net.autosetup()
print("WLAN STATUS: ", ssid, ifconfig[0])

######## RPC ########
rpc = RPC()
rpc.register(dev.setpwm)
rpc.register(dev.getadc)


@rpc.register
def listall():
    return list(rpc.functions)


######## OLED ########
i2cdev = I2C(conf.I2CBUSID, freq=1000_000)
XRES, YRES = 128, 32
oled = SSD1306_I2C(XRES, YRES, i2cdev)
sleep_ms(100)


def info2oled(pagenums=[]):
    """if pagenum is a positive number, then
    only that specific page will be updated
    instead of updating the whole oled which
    is slow because of writing the entire
    framebuffer into the oled Display RAM"""

    oled.fill(0)  # all black
    # oled.show()

    oled.text(f"SSID:{ssid}", 0, 0)
    oled.text(
        f"{ifconfig[0]}", 0, 8
    )  # characters are 8 pixels in height, hence we need to start at y=8

    oled.text(f"ADC: {dev.getadc()}", 0, 16)
    oled.text(f"PWM: {dev.motorduty}", 0, 24)

    if len(pagenums) > 0:  # only update the give pagenums
        for pn in pagenums:
            oled.show_page(pn)
    else:
        oled.show()


######## CALIBRATE ########
def getcalibvals():
    # wait till button is pressed
    while dev.readbtn():
        oled.fill(0)
        oled.text(f"map -90deg: {dev.getadc()}", 0, 16)
        oled.show()
    neg90potval = dev.getadc()  # read and set

    while dev.readbtn():  # wait again
        oled.fill(0)
        oled.text(f"map -90deg: {neg90potval}", 0, 16)
        oled.text(f"map +90deg: {dev.getadc()}", 0, 24)
        oled.show()
    pos90potval = dev.getadc()

    sleep_ms(1000)  # keep the info on the oled for 1 sec for user to read.

    calib = {"neg90potval": neg90potval, "pos90potval": pos90potval}

    # save to file/flash for non-volatility and load on next boot
    with open("calibration.json", "w") as g:
        g.write(json.dumps(calib))

    return calib


def calibrate():
    # clear the last 2 lines/pages
    # oled.text(" " * (128 // 8), 0, 16)
    # oled.text(" " * (128 // 8), 0, 24)
    oled.fill(0)
    oled.show()

    calfile = "calibration.json"
    if calfile not in os.listdir():
        calib = getcalibvals()  # ask to set
    else:
        calib = json.load(open(calfile))  # retrive previous setting

        then = time()

        USER_RESPOND_TIMELIMIT = 7  # in seconds
        while (
            time_remaining := time() - then
        ) < USER_RESPOND_TIMELIMIT:  # check btn press for 5 seconds
            if dev.readbtn() == 0:  # btn pressed
                calib = getcalibvals()
                break
            # prompt if they want to recalibrate
            oled.fill(0)
            oled.text(f"press btn..({USER_RESPOND_TIMELIMIT - time_remaining}s)", 0, 16)
            oled.text("..to recalibrate", 0, 24)
            oled.show()

    return calib


####### APP INIT #######
def init():
    # starting buzz
    dev.buzz(50)
    sleep_ms(50)
    dev.buzz(50)
    sleep_ms(100)
    dev.buzz(100)
    # initilize info to oled
    info2oled()

    # get calibration vals
    calib = calibrate()
    oled.fill(0)
    oled.text("Calibrated...", 0, 16)
    oled.show()
    sleep_ms(1000)  # give user 1 sec to read the oled


######## APP RUN ########
SKIPVAL = 2500


def run():
    skip = SKIPVAL
    while True:
        rpc.handle(timeout=0)
        # this write to oled takes non-significant
        # time which leads to poor lagged feedback,
        # hence we call this only once in a while

        if skip == SKIPVAL:
            info2oled([2, 3])
            skip = 0
        else:
            skip += 1
