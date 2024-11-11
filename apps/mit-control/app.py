from machine import Pin, PWM, ADC
import conf
from udprpc import RPC


class Device:
    def __init__(self, motpin, potpin):
        self.motor = PWM(Pin(motpin), freq=20000)
        self.pot = ADC(potpin)

    def setpwm(self, val):
        return motor.duty_us(val)

    def getadc(self):
        return pot.read_u16() // 2**6


def start():
    rpc = RPC()
    dev = Device(conf.MOTPIN, conf.POTPIN)
    rpc.register(dev.setpwm)
    rpc.register(dev.getadc)
    while True:
        rpc.handle()
