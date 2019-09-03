import time
import math
import os
import machine
import esp
import esp32
import ntptime
import ssd1306
import network
import gc

from machine import I2C, Pin, ADC


# base utils


def remove_empty(lst):
	return list(filter(None, lst))	# https://stackoverflow.com/a/3845453

def text_height(text) -> int:
	return 10*(text.count('\n') + 1)	# 1 line = 10px

def text_width(text):
	# note: because this accounts for spacing, it includes 2 extra "transparent" pixels at the end of the text
	# returns width of farthest stretching line
	
	lines = text.split('\n')
	lines = remove_empty(lines)
	line_lens = [len(line) for line in lines]
	
	# 6px wide char + 2px wide spacing after char
	return 8 * max(line_lens)


def file_exists(path):
	try:
		os.stat(path)
		return True
	except OSError:
		return False

# MARK - Network Utils
CONNECT_MAX_TRIES = 3	# iterations

def get_network_cfgs():
	network_cfgs = []
	if file_exists("networks.txt"):
		with open("networks.txt") as f:
			for line in f.readlines():
				line = line.replace('\n', '') \
							 .replace(' ', '') \
							 .replace('\r', '')

				
				cfg = tuple(line.split(":")[0:2])
				network_cfgs.append(cfg)
	
	print("got cfgs" + str(network_cfgs))
	return network_cfgs


def do_connect(wlan, essid, passwd) -> bool:
	connect_iterations = 0
	
	if not wlan.isconnected():
		wlan.connect(essid, passwd)
		while not wlan.isconnected():
			machine.lightsleep(100)	# wait 100 ms for the device to connect
			connect_iterations += 1
			print(connect_iterations)
			if connect_iterations >= CONNECT_MAX_TRIES:
				return False
		
		return wlan.isconnected()	# should always be true

def do_connect_all(wlan):	
	if not wlan.isconnected():
		print('connecting to network...')
		network_cfgs = get_network_cfgs()
		
		if(network_cfgs):
			print("Found network cfg, file")
			for (essid, passwd) in network_cfgs:
				print("Using " + essid + passwd)
				success = do_connect(wlan, essid, passwd)
				print("Connect success:" + str(success))
				if(success): 
					print("Sucessfully connected to network")
					return
		else:
			print("No network cfg found: defaulting to searching for an open network")
			# todo
			

	print('network config:', wlan.ifconfig())

def clear():
	oled.fill(0)

def clear_text_at(oled, x, y, text):
	oled.fill_rect(x, y, x+text_width(text), y+text_height(text), 0)

def draw_text(oled, text, x, y):
	clear_text_at(oled, x, y, text)
	oled.text(text, x, y)

def draw_temp(oled, x, y):
	# todo add icon?
	temp_str = ""
	#temp_str += "TEMP:"
	temp_str += "{0:3d}".format(esp32.raw_temperature())
	temp_str += "F"
	draw_text(oled, temp_str, x, y)

def draw_hall(oled, x, y):
	hall_str = ""
	hall_str += "HALL"
	hall_str += "{:02d}".format(esp32.hall_sensor())
	draw_text(oled, hall_str, x, y)

def isBerkanBDAY(datetime):
	year, month, day, _, _, _, _, _ = datetime
	# if year is 2019, then special exception for 9/2/2019 counting as bday
	if year == 2019:
		if month == 9 and day == 2:
			return True
	else:
		if month == 8 and day == 24:
			return True
	
	return False

# oled utils

def draw_icon(oled, icon, x_offset, y_offset):
	# from https://www.twobitarcade.net/article/oled-displays-i2c-micropython/
	# where icon is a 2d int array
	for y, row in enumerate(icon):
		for x, c in enumerate(row):
			oled.pixel(x_offset + x, y_offset + y, c)


def draw_time(oled, x, y):
	time_str = ""
	hour, min, sec = rtc.datetime()[4:7]
	# dirty hack to get the time right. the ntp is off by four hours
	time_str += "{:02d}".format((hour - 4) % 12)	# 2 digit zeropad
	
	# adds a blinking colon every second
	if sec % 2 == 0:
		time_str += ":"
	else:
		time_str += " "
	
	time_str += "{:02d}".format(min)
	
	clear_text_at(oled, x, y, time_str)
	oled.text(time_str, x, y)
		
def hbd_pos(t, msg_len):
	max_period = 8*msg_len	 # magic formula for determining best duration of scrolling such that all text is cscrolled over
	norm_t = t % max_period
	return -(norm_t)

def draw_happybday(oled, x, y):
	# todo x y pos
	oled.text(HBD_MSG, x, y)

# main code
rtc = machine.RTC()
i2c = I2C(scl=Pin(22), sda=Pin(23))
print(i2c.scan())
oled = None
oled = ssd1306.SSD1306_I2C(128, 32, i2c)


HBD_MSG = 'HAPPY BDAY BERKAN!'

def main():
	# MAIN RENDER LOOP
	clear()
	HBD_X = int(128 *(0/10))
	HBD_Y = 10
	
	T_MAX = 2**15

	t = 0

	NTP_SET = False

	wlan = network.WLAN(network.STA_IF)
	wlan.active(True)
	do_connect_all(wlan)
	oled.text("BOOTING", 0, 0)
	oled.show()
	bootx = 0
	booty = 0
	boot_str = ""
	
	MAX_WLAN_RETRIES = 10
	WLAN_RETRIES = 0

	while not wlan.isconnected():
		time.sleep(4)
		if WLAN_RETRIES >= MAX_WLAN_RETRIES:
			break
		else:
			WLAN_RETRIES += 1
	
	# for i in range(100):
	# 	for attempt in range(10):
	# 		try:
	# 			print("Trying settime")
	# 			ntptime.settime()
	# 		except:
	# 			print("Couldn't settime, retrying")				
	# 		else:
	# 			break
	# 	else:
	# 		print("Error: Couldn't settime")

	clear()
	print("About to enter loop")
	while 1:
		# print("in loop")
		if(NTP_SET):
			if(isBerkanBDAY(rtc.datetime())):
				clear_text_at(oled, 0, 0, HBD_MSG)
				draw_happybday(oled, hbd_pos(t, len(HBD_MSG)), 0)
		else:
			clear_text_at(oled, 0, 0, HBD_MSG)
			draw_happybday(oled, hbd_pos(t, len(HBD_MSG)), 0)

		draw_temp(oled, 0, 32-text_height("000F"))
		oled.text(" |", text_width("000F"), 32 - text_height("|"))
		draw_time(oled, text_width("000X") + text_width(" |") + 2, 32-text_height("00:00"))
		

		# draw_hall(oled, 0 + text_width("_HALL"), 20) # it's kinda useless tbh
		oled.show()

		if not NTP_SET:
			try:
				ntptime.settime()
				if rtc.datetime()[0] > 2000:
					NTP_SET = True
			except:
				gc.collect()


		t += 1
		t %= T_MAX

