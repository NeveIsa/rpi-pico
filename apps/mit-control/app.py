from machine import Pin, PWM, ADC
import conf
from udprpc import RPC


class Device:
    def __init__(self, motpin, potpin):
        self.motor = PWM(Pin(motpin), freq=20000)
        self.pot = ADC(Pin(potpin))

    def setpwm(self, val):
        return self.motor.duty_u16(val)

    def getadc(self):
        return self.pot.read_u16() // 2**6


# MAIN #
rpc = RPC()
dev = Device(conf.MOTPIN, conf.POTPIN)
rpc.register(dev.setpwm)
rpc.register(dev.getadc)


def run():
    while True:
        rpc.handle()
