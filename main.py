import upip
import math

import network
import machine
import utime

import config as conf


class StoreController:

	CIRCUMFERENCE_M = 2 * math.pi * 20 / 1000
	MAX_SPEED = 1
	MAX_GUST = 0.8

	def __init__(self):
		pin = machine.Pin(2, machine.Pin.OUT)
		self._led = machine.Signal(pin, invert=True)
		self._wlan = self.connectWlan()

		if self._wlan:
			upip.install('urequests')

		self._led.off()

		self._blindOpen = False
		self._counter = 0
		self._gustCounter = 0
		self._notificationCooldown = 0

		self._hallSensor = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
		self._hallSensor.irq(handler=self.onHallSensor, trigger=machine.Pin.IRQ_RISING)

		self._switchSensor = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
		self._switchSensor.irq(handler=self.onSwitch, trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING)
		self._switchTicks = utime.ticks_ms()
		# 1 = store ouvert
		# 0 = store fermé

		if self._switchSensor.value():
			self._blindOpen = True
			self.measureWindSpeed()


	def onSwitch(self, pin: machine.Pin):
		now = utime.ticks_ms()
		if now < self._switchTicks + 50:
			return

		self._switchTicks = now

		if pin.value():
			self._blindOpen = True
			print('open')
		elif not pin.value():
			print('closed')
			self._blindOpen = False
			machine.idle()


	def measureWindSpeed(self):
		i = 0
		ms = 0
		kmh = 0
		while True:
			i += 1
			self._gustCounter = 0
			utime.sleep(5)

			if not self._blindOpen:
				utime.sleep(60)
				self._counter = 0
				self._gustCounter = 0
				i = 0
				continue

			gust_ms, gust_kmh = self.calculateWind(self._gustCounter, 5)

			if i >= 12:
				i = 0
				ms, kmh = self.calculateWind(self._counter, 60)
				self._counter = 0
			elif ms == 0:
				ms = gust_ms
				kmh = gust_kmh

			print('Wind speed: ', ms, 'm/s ,', kmh, 'km/h. Wind gusts at ', gust_ms, 'm/s,', gust_kmh, 'km/h')

			if ms > self.MAX_SPEED:
				# roll up the blind!
				if self._wlan and (self._notificationCooldown == 0 or self._notificationCooldown >= 720):
					self._notificationCooldown = 1
					for key in conf.ifttt.values():
						link = 'https://maker.ifttt.com/trigger/store_gust/with/key/' + key + '?value1=' + str(round(ms, 2)) + '&value2=' + str(round(gust_ms, 2))
						import urequests
						urequests.get(link)

			if self._notificationCooldown > 0:
				self._notificationCooldown += 1


	def calculateWind(self, spin: int, time: int) -> tuple:
		if time <= 0:
			time = 1

		ms = ((spin / 3) * self.CIRCUMFERENCE_M) / time
		kmh = ms * 3.6
		return ms, kmh


	def onHallSensor(self, pin: machine.Pin):
		self._counter += 1
		self._gustCounter += 1


	def connectWlan(self) -> network.WLAN:
		wlan = network.WLAN(network.STA_IF)
		wlan.active(True)

		availableNetworks = set()
		scan = wlan.scan()
		for result in scan:
			try:
				ssid = result[0].decode('utf-8')
			except:
				ssid = result[0]
			finally:
				availableNetworks.add(ssid)

		i = 0
		if not wlan.isconnected():
			print('Connecting wlan')
			for ssid, password in conf.networks.items():
				if ssid not in availableNetworks:
					continue

				wlan.connect(ssid, password)
				while not wlan.isconnected():
					i += 1
					if i > 1000:
						print('Failed connecting to wlan', ssid)
						break
					machine.idle()

				if wlan.isconnected():
					break

			if not wlan.isconnected():
				print('Connecting to wlan failed... Status: ', wlan.status())
				j = 0
				while j < 10:
					if self._led.value():
						self._led.off()
					else:
						self._led.on()
					j += 1
					utime.sleep_ms(500)
				return None

		print('Connected to wlan with ip', wlan.ifconfig()[0], 'to', wlan.config('essid'))
		j = 0
		while j < 50:
			if self._led.value():
				self._led.off()
			else:
				self._led.on()
			j += 1
			utime.sleep_ms(50)
		return wlan


if __name__ == '__main__':
	print('Starting blind controller')
	StoreController()
