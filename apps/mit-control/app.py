from machine import Pin, PWM, ADC, I2C
from ssd1306 import SSD1306_I2C
import conf
from udprpc import RPC
from time import sleep_ms
import net


class Device:
    def __init__(self, motpin, potpin):
        self.motor = PWM(Pin(motpin), freq=20000)
        self.pot = ADC(Pin(potpin))
        self.motorduty = 0

    def setpwm(self, val):
        self.motorduty = val
        return self.motor.duty_u16(val)

    def getadc(self):
        return self.pot.read_u16() // 2**6


# NETWORK #
ssid, ifconfig = net.autosetup()
print("WLAN STATUS: ", ssid, ifconfig[0])

# RPC #
rpc = RPC()
dev = Device(conf.MOTPIN, conf.POTPIN)
rpc.register(dev.setpwm)
rpc.register(dev.getadc)


@rpc.register
def listall():
    return list(rpc.functions)


# OLED #
i2cdev = I2C(conf.I2CBUSID, freq=1000_000)
XRES, YRES = 128, 32
oled = SSD1306_I2C(XRES, YRES, i2cdev)
sleep_ms(100)


def info2oled():
    oled.fill(0)  # all black
    # oled.show()

    oled.text(f"SSID:{ssid}", 0, 0)
    oled.text(
        f"{ifconfig[0]}", 0, 8
    )  # characters are 8 pixels in height, hence we need to start at y=8

    oled.text(f"ADC: {dev.getadc()}", 0, 16)
    oled.text(f"PWM: {dev.motorduty}", 0, 24)

    oled.show()


info2oled()


# RUN #
SKIPVAL = 2500
def run():
    skip = SKIPVAL
    while True:
        rpc.handle(timeout=0)
        # this write to oled takes non-significant
        # time which leads to poor lagged feedback,
        # hence we call this only once in a while

        if skip == SKIPVAL:
            info2oled()
            skip = 0
        else:
            skip += 1
