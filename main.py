import datetime
import io
import math
import os
import picamera
from PIL import Image, ImageChops, ExifTags
import pygame
from pygame.locals import *
import re
from subprocess import call
import sys
import threading
import time
import traceback

# Init framebuffer/touchscreen environment variables
# os.putenv('SDL_VIDEODRIVER', 'fbcon')
# os.putenv('SDL_FBDEV'      , '/dev/fb1')
# os.putenv('SDL_MOUSEDRV'   , 'TSLIB')
# os.putenv('SDL_MOUSEDEV'   , '/dev/input/touchscreen')


# --- Global variables -----------------------------------------


global camera, cam_buffer_rgb, capturing, current_setting, settings, timers, do_exit
global output_folder, images, current_image
global screen, gui_update, gui_mode, gui_font, colors, display_size

output_folder = '../DCIM/'
images = []  # list of images in output_folder
current_image = {
	'index': 99999,     # very high number, so after limiting always picks latest image
	'index_loaded': -1, # non-plausible number
	'filename': None,
	'video': False,
	'fps': 0,
	'active': False,
	'img': None,        # pygame surface (original resolution)
	'img_scaled': None, # pygame surface (based on scaled img)
}

display_size = (1360, 768)  #(320,240)

screen = None
gui_update = {
	'dirty': True,    # True if display should be refreshed
	'full': True,     # True if FULL display should be refreshed
	'rectangles': []  # partial display updates can indicate pygame rectangles to redraw
}
gui_font = None
gui_mode = 0
colors = {
	'white':   pygame.Color(255, 255, 255),
	'black':   pygame.Color(0, 0, 0),
	'support': pygame.Color(214, 0, 50)
}

settings = {}
current_setting = 'shutter_speed'
do_exit = False
timers = {
	'settings':      None,  # after some time on a settings menu, return to default
	'camera_ready':  None,  # wait before camera is ready for capture
	'camera_standy': None,  # after some time, close camera object
	'standy':        None,  # after some time, put system to standby mode (0)
	'capturing':     None   # keep time since capturing started
}

camera = None
capturing = False

# buffer for viewfinder data
cam_buffer_rgb = bytearray(display_size[0] * display_size[1] * 3)  # x * y * RGB


# --- Settings functions ----------------------------------------


# initiate all program and camera settings
def settings_init ():
	global settings

	settings = {
		'menu': Setting(99, 'Menu', None, 0, [0], [0], menu=False),
		'iso': Setting(1, 'ISO', 'iso', 1,
				[     0, 100, 200, 320, 400, 500, 640, 800],
				['auto', 100, 200, 320, 400, 500, 640, 800],
				menu=False, exif='EXIF.ISOSpeedRatings'),
		'shutter_speed': SettingShutter(2, 'Shutter speed', 'shutter_speed', 36,
			[0, 1/4000.0, 1/3200.0, 1/2500.0, 1/2000.0, 1/1600.0, 1/1250.0, 1/1000.0, 1/800.0, 1/640.0, 1/500.0,
				1/400.0, 1/320.0, 1/250.0, 1/200.0, 1/160.0, 1/125.0, 1/100.0, 1/90.0, 1/80.0, 1/60.0, 1/50.0, 1/40.0,
				1/30.0, 1/25.0, 1/20.0, 1/15.0, 1/13.0, 1/10.0, 1/8.0, 1/6.0, 1/5.0, 1/4.0, 1/3.0, 1/2.5, 1/2.0,
				1/1.6, 1/1.3, 1, 1.3, 1.6, 2, 2.5, 3, 4, 5, 6, 8, 10, 13, 15],
			['auto', '1/4000', '1/3200', '1/2500', '1/2000', '1/1600', '1/1250', '1/1000', '1/800', '1/640', '1/500',
				'1/400', '1/320', '1/250', '1/200', '1/160', '1/125', '1/100', '1/90', '1/80', '1/60', '1/50', '1/40',
				'1/30', '1/25', '1/20', '1/15', '1/13', '1/10', '1/8', '1/6', '1/5', '1/4', '1/3', '1/2.5', '1/2',
				'1/1.6', '1/1.3', '1', '1.3', '1.6', '2', '2.5', '3', '4', '5', '6', '8', '10', '13', '15'],
				menu=False, exif='EXIF.ShutterSpeedValue'),
		'exposure_compensation': Setting(3, 'Exposure compensation', 'exposure_compensation', 0, (-25,25),
			menu=False, exif='EXIF.ExposureBias'),
		'framerate': SettingFramerate(4, 'Framerate', 'framerate', 15, (1,15), menu=False),
		'exposure_mode': Setting(5, 'Exposure Mode', 'exposure_mode', 2, [
			'off',
			'auto',
			'night',
			#'nightpreview',
			#'backlight',
			#'spotlight',
			#'sports',
			#'snow',
			#'beach',
			'verylong',
			'fixedfps',
			#'antishake',
			#'fireworks'
			], exif='EXIF.ExposureMode'),
		'awb_mode': Setting(6, 'White balance mode', 'awb_mode', 1, [
			'off',
			'auto',
			'sunlight',
			'cloudy',
			'shade',
			'tungsten',
			'fluorescent',
			'incandescent',
			'flash',
			'horizon'], exif='EXIF.WhiteBalance'),
		# 'meter_mode': Setting(7, 'Metering', 'meter_mode', 0, ['average','spot','backlit','matrix'],
		# 	exif='EXIF.MeteringMode'),
		# Image effect list below is taken from camera.IMAGE_EFFECTS minus several
		# that cause trouble (##) or have no useful effect (#)
		'image_effect': Setting(8, 'Image effect', 'image_effect', 0, [
			'none',
			'negative',
			'solarize',
			##'posterize',
			##'whiteboard',
			##'blackboard',
			'sketch',
			#'denoise',
			'emboss',
			'oilpaint',
			'hatch',
			'gpen',
			'pastel',
			'watercolor',
			'film',
			#'blur',
			##'saturation',
			'colorswap',
			'washedout',
			'posterise',
			##'colorpoint',
			##'colorbalance',
			'cartoon']),
		# 'sharpness':  Setting( 9, 'Sharpness',  'sharpness',   0, (-100,100), exif='EXIF.Sharpness'),
		# 'contrast':   Setting( 10, 'Contrast',   'contrast',    0, (-100,100), exif='EXIF.Contrast'),
		# 'brightness': Setting(11, 'Brightness', 'brightness', 50, (0,100), exif='EXIF.BrightnessValue'),
		# 'saturation': Setting(12, 'Saturation', 'saturation',  0, (-100,100), exif='EXIF.Saturation'),
		'vflip': Setting(20, 'Flip image vertically',   'vflip', 1, [False, True], ['off', 'on']),
		# 'hflip': Setting(21, 'Flip image horizontally', 'hflip', 0, [False, True], ['off', 'on']),
		'mode': SettingMode(96, 'Mode', 'resolution', 0, [
				[(2592,1944), (1.0/6, 15), 'Still'],
				[(1296, 972), ( 6,  6), 'Video 4:3 972p  6fps'],   # 1-42 fps
				[(1296, 972), (12, 12), 'Video 4:3 972p 12fps'],
				[(1296, 972), (24, 24), 'Video 4:3 972p 24fps'],
				[(1296, 972), (30, 30), 'Video 4:3 972p 30fps'],
				[( 640, 480), (60, 60), 'Video 4:3 480p 60fps'],   # 43-90 fps
				[( 640, 480), (90, 90), 'Video 4:3 480p 90fps'],
				[(1296, 730), (24, 24), 'Video 16:9 730p 24fps'],  # 1-49 fps
				[(1296, 730), (30, 30), 'Video 16:9 730p 30fps'],
				[(1296, 730), (48, 48), 'Video 16:9 730p 48fps'],
				[(1920,1080), (24, 24), 'Video 16:9 1080p 24fps'], # (partial FOV)
				[(1920,1080), (30, 30), 'Video 16:9 1080p 30fps']  # 1-30 fps
			]),
		#'delay': Setting(30, 'Shutter delay', None, 0, (0,30)),
		#'interval': Setting(31, 'Interval', None, 0, [False, True], ['off', 'on']),
		#'preview_mode': Setting(40, 'Preview mode', None, 0, [0, 1, 3], ['normal', 'histogram', 'sharpness']),
		'review': Setting(41, 'Review after capture', None, 0, [False, True], ['off', 'on']),
		# 'camera_led': Setting(97, 'Camera LED', 'led', 1, [False, True], ['off', 'on']),
		#'power': Setting(98, 'Power', None, 1, [False, True], ['off', 'on'])
	}
	# setup menu items
	settings['menu'].range = []
	settings['menu'].range_display = []
	for key in settings:
		if settings[key].in_menu:
			settings['menu'].range.append(key)
	settings['menu'].range = sorted(settings['menu'].range, cmp=order_compare)
	for key in settings['menu'].range:
		settings['menu'].range_display.append(settings[key].get_name())


# utility function to order a list of settings according to order value
def order_compare (x, y):
	global settings
	return settings[x].order - settings[y].order


class Setting:
	def __init__ (self, order=0, name='SettingName', name_real=None, state=0,
					in_range=[], range_display=None, menu=True, exif=None):
		self.order = order
		self.name = name
		self.name_real = name_real
		self.exif = exif
		self.state = state
		self.min = None
		self.max = None
		self.range = None
		self.range_display = None
		if (isinstance(in_range, tuple)):
			self.min = in_range[0]
			self.max = in_range[1]
		else:
			self.range = in_range
			if (range_display is not None):
				self.range_display = range_display
			else:
				self.range_display = self.range
		self.value = in_range[0]  # reasonable starting value?
		self.in_menu = menu
		self.set_state(0)

	def get_name (self):
		return self.name

	def get_name_real (self):
		return self.name_real

	def get_state (self):
		return self.state

	# n is -1 or 1 depending on direction, 0 means no change
	def set_state (self, n=0):
		if (self.range is None):
			self.value = min(max(self.state + n, self.min), self.max)
			self.state = self.value
		# ordered values
		else:
			self.state = min(max(self.state + n, 0), len(self.range)-1)
			self.value = self.range[self.state];

		# apply value to camera
		self.apply_value()

	# figure out state from position in range [0,1]
	def set_state_from_position (self, position):
		# figure out state closest to position
		state = self.state  # assume no change
		if (self.range is not None):
			state = int(position * (len(self.range) - 0))
		else:
			state = int((self.max - self.min) * position + self.min)
		# diff current state and desired state -> n
		n = state - self.state
		self.set_state(n)

	# sets the camera to current value
	def apply_value (self):
		global camera

		# some properties have no read method and
		# would trip on the getattr call below
		if (self.name_real == 'led'):
			setattr(camera, self.name_real, self.value)
		elif (self.name_real is not None):
			# check value of attribute of camera object
			# only update if necessary to prevent camera restarts
			do_apply = True

			# fps uses Fraction values which may differ due to floating point calculations
			# solved by checking for a difference that is small enough to be considered equal
			if (self.name_real == 'framerate'):
				diff = abs(self.value - 1.0 * getattr(camera, self.name_real))
				if (diff < 0.001):
					do_apply = False
			elif (self.value == getattr(camera, self.name_real)):
				do_apply = False
			
			if (do_apply):
				setattr(camera, self.name_real, self.value)

		if (self.exif is not None):
			camera.exif_tags[self.exif] = str(self.value)

		# if (self.name_real == 'iso'):
		# 	print "ISO      setting: ", self.value
		# 	print "ISO  analog gain: ", 1.0 * camera.analog_gain
		# 	print "ISO digital gain: ", 1.0 * camera.digital_gain

		# if (self.name_real == 'awb_mode'):
		# 	time.sleep(2)
		# 	print "AWB  mode: ", self.value
		# 	print "AWB gains: ", 1.0*camera.awb_gains[0], 1.0*camera.awb_gains[1]

	# only set value directly when known to be valid (no checking is done)
	def set_value (self, value):
		self.value = value
		self.apply_value()

	def get_value (self, string=False):
		if (string):
			# continuous value
			if (self.range is None):
				if (self.name_real == 'exposure_compensation'):
					string = str(round(1.0 * self.value / 6, 1))  # steps of 1/6 EV
					if (self.value > 0):
						string = '+' + string
					return string
				else:
					return str(self.value)
			# ordered values
			else:
				return str(self.range_display[self.state])
		else:
			return self.value

	def set_range (self, in_range):
		if (isinstance(in_range, tuple)):
			self.min = in_range[0]
			self.max = in_range[1]
			self.range = None
			self.range_display = None
		else:
			self.range = in_range
			if (self.range_display is not None):
				self.range_display = range_display
			else:
				self.range_display = self.range

		# make sure current state/value is within new range
		self.set_state(0)

	def get_range (self):
		return self.range

	def get_range_display (self):
		return self.range_display

	def get_min (self):
		return self.min

	def get_max (self):
		return self.max

	# return position within range as float value in [0,1]
	def get_position (self):
		if (self.range is None):
			return 1.0 * (self.value - self.min) / (self.max - self.min)
		else:
			return max(min(1.0 * self.state / (len(self.range) - 1), 1.0), 0.0)

	def get_nearby_value (self, in_value, display=False, in_index=False):
		if (self.range is None):
			return in_value  # not really implemented...
		else:
			# find index in range that is closest
			closest_index = -1
			diff = 9999999
			for i in range(0, len(self.range)):
				temp_diff = abs(self.range[i] - in_value)
				if (temp_diff < diff):
					closest_index = i
					diff = temp_diff
			# return the value
			if (in_index):
				return closest_index
			elif (closest_index == -1):  # search was unsuccessful
				return in_value
			elif (display):
				return self.range_display[closest_index]
			else:
				return self.range[closest_index]


class SettingShutter (Setting):

	def set_state (self, n=0):
		global settings

		self.state = max(self.state + n, 0)
		# make sure ss does not exceed minimum fps (longest shot possible) in any video mode
		try:
			if (settings['mode'].is_still() is not True):
				max_ss = 1.0 / settings['framerate'].get_min()
				while(self.range[self.state] > max_ss):
					self.state -= 1
		except:
			pass


		# ss gets values from predefined array or, if it exceeds that, incremental values
		if (self.state <= len(self.range)-1):
			self.value = int(self.range[self.state] * 1000000)  # convert to microseconds
		else:
			# add or subtract 5 seconds per tick (no upper limits)
			# + convert to microseconds
			self.value = (15 + (self.state - len(self.range)+1) * 5) * 1000000

		# RaspiCam only supports shutter speeds up to 6 seconds.
		# longer exposures thus need be composites of several shots in rapid succession.
		if (self.value < 6000000):
			self.value_per_shot  = self.value
			self.number_of_shots = 1
		else:
			self.number_of_shots = int(math.ceil(self.value / 6000000.0))
			self.value_per_shot  = self.value / self.number_of_shots

		# apply value to camera
		self.apply_value()

	def set_state_from_position (self, position):
		if (settings['mode'].is_still()):
			Setting.set_state_from_position(self, position)
		else:
			state = self.state
			
			# convert from shutter angle to ss
			ss_per_shot = 1.0 * position / settings['framerate'].get_value()
			state = self.get_nearby_value(ss_per_shot, in_index=True)
			
			n = state - self.state
			self.set_state(n)

	# sets the camera to current value
	def apply_value (self):
		global settings

		Setting.apply_value(self)
		# force framerate to update as well, as shutter speed is dependent on that
		# note: framerate setting may not yet be initialised, hence the try block
		try:
			settings['framerate'].set_state()
		except:
			pass
			
	def get_value (self, string=False, per_shot=False):
		if (per_shot):
			if (string):
				return str(self.value_per_shot / 1000000.0)
			else:
				return self.value_per_shot
		elif (string):
			if (self.state <= len(self.range)-1):
				return self.range_display[self.state]
			else:
				ssDisplay = 15 + (self.state - len(self.range)+1) * 5
				# make display for anything over a minute a little nicer
				if (ssDisplay >= 60):
					ssSeconds = ssDisplay % 60
					if (ssSeconds < 10):
						ssSeconds = '0' + str(ssSeconds)
					ssDisplay = str(ssDisplay / 60) + 'm' + str(ssSeconds)
				return str(ssDisplay)
		else:
			return self.value

	def get_shots (self):
		return self.number_of_shots

	# @return for video gives shutter angle: exposure time / frame interval in range [0,1]
	def get_position (self):
		if (settings['mode'].is_still()):
			return Setting.get_position(self)
		else:
			# ss * fps = ss / (1/fps)
			return (self.value_per_shot / 1000000.0) * settings['framerate'].get_value()


# Framerate requires override of default class for its dependent state.
# framerate is limited both by mode (e.g., still mode has a max of 15 fps)
# and video has a fixed fps during capture (as changing framerate requires a restart)
class SettingFramerate(Setting):
	# value of n is ignored, but kept in for compatibility with regular Setting.set_state
	def set_state (self, n=0):
		global settings

		# calculate fps value based on current shutterspeed
		# note: ss setting may not yet be initialised, hence the try block
		ss = 0.1
		try:
			ss = settings['shutter_speed'].get_value(per_shot=True) / 1000000.0
		except:
			pass
		fps = 1.0 / ss
		# value gets capped by the min and max fps
		self.value = max(self.min, min(self.max, fps))

		# apply value to camera if altered
		self.apply_value()

	def set_range (self, in_range):
		global settings

		Setting.set_range(self, in_range)
		# upon setting the new range, also get ss to stay within limits if necessary
		try:
			settings['shutter_speed'].set_state(0)
		except:
			pass


# in_range: [(tuple, resolution), (tuple, fps limits), 'NameString']
class SettingMode(Setting):

	def __init__ (self, order=0, name='SettingName', name_real=None, state=0, in_range=[], menu=True):
		self.order = order
		self.name = name
		self.name_real = name_real
		self.state = state
		self.range = in_range
		self.in_menu = menu
		self.set_state(0)

	def apply_value (self):
		global settings, cam_buffer_rgb

		# update camera resolution
		if (self.value[0] != getattr(camera, self.name_real)):
			setattr(camera, self.name_real, self.range[self.state][0])
			# make sure buffer is equal to new resolution
			cam_buffer_rgb = bytearray(self.value[0][0] * self.value[0][1] * 3)

		# restrict framerate to current mode's limits
		# note: framerate setting may not yet be initialised, hence the try block
		try:
			settings['framerate'].set_range( self.range[self.state][1] )
		except:
			pass

	def get_value (self, string=False, short=False):
		# returns name of mode in short: e.g., 480p24
		if (string and short):
			if (self.state == 0):
				return self.range[self.state][2]  # name: still
			else:
				return str(self.range[self.state][0][1]) + 'p' + settings['framerate'].get_value(True)
		if (string):
			return self.range[self.state][2]  # name of mode
		else:
			return self.range[self.state][0]  # resolution

	def is_still (self):
		return (self.state == 0)


def do_settings_active (state=True):
	global gui_mode, timers 

	if (state):
		set_gui_mode(2)
		# activate timer to deactive state after a delay
		timers['settings'] = time.time() + 10
	else:
		set_gui_mode(1)
		timers['settings'] = None


def set_current_setting (setting=None):
	global current_setting

	current_setting = setting
	do_current_setting(0)


def get_current_setting (name=False):
	global current_setting, settings

	if name is not True:
		return current_setting
	else:
		return settings[current_setting].get_name()


# confirms + deactivates the current setting
def do_current_confirm ():
	global current_setting, gui_update

	# make sure main menu confirmation dives into submenu
	if (current_setting == 'menu'):
		set_current_setting(get_current_value())
	# otherwise, confirm and deactivate menu
	else:
		do_settings_active(False)
	# make sure any changes are reflected on screen
	gui_update['dirty'] = True


# passes on the adjustment to the currently active setting
def do_current_setting (n=0, position=None):
	global current_setting, settings, gui_update

	do_settings_active(True)
	if (position is None):
		settings[current_setting].set_state(n)
	else:
		settings[current_setting].set_state_from_position(position)
	# make sure any changes are reflected on screen
	gui_update['dirty'] = True


# gets the value for the current setting
def get_current_value (string=False):
	global current_setting, settings
	return settings[current_setting].get_value(string)


# gets position of current setting's value in range [0,1]
def get_current_position ():
	global current_setting, settings
	return settings[current_setting].get_position()


# --- Image viewing functions ----------------------------------

def load_images_list ():
	global images, current_image, output_folder

	images = []  # reset first
	for file in os.listdir(output_folder):
		if (file.endswith('.jpg') or file.endswith('.h264')):
			images.append(file)
	images.sort()

	# in case an image was deleted, make sure current_image is not out of bounds
	current_image['index'] = min(max(current_image['index'], 0), len(images)-1)


# n gives direction (-1: earlier image, 1: next image)
def set_current_image (n=0, latest=False):
	global current_image, images, gui_update
	if (latest):
		current_image['index'] = len(images)-1
		gui_update['dirty'] = True
	elif (n != 0):
		current_image['index'] = min(max(current_image['index'] + n, 0), len(images)-1)
		gui_update['dirty'] = True


def set_image_active (state=None):
	global current_image, gui_update

	if (state is None):
		current_image['active'] = not current_image['active']
	else:
		current_image['active'] = state

	gui_update['dirty'] = True


# --- Camera functions ----------------------------------------


# @restart: can be used to re-init the camera after it was terminated
def camera_init (restart=False, forced=False):
	global camera, settings, display_size, timers

	timers['camera_standby'] = None  # reset

	if (camera is None or camera.closed is True):
		camera = picamera.PiCamera()
		
	# re-apply all values to the new, set-to-defaults camera object
	if (restart or forced):
		for key in settings:
			settings[key].apply_value()
		# also set some EXIF tags that are not linked to a setting
		#camera.exif_tags['IFD0.Make'] = "RaspberryPi"  # default
		camera.exif_tags['IFD0.Model'] = "Pi Viewcam"
		
	# make sure to give camera some time to get ready
	timers['camera_ready'] = time.time() + 2


# stops the camera, which can no longer be used
# make sure to call camera_init first after that happens
def camera_close ():
	global camera, timers

	timers['camera_standby'] = None  # reset
	set_preview(False)
	camera.close()


# Makes sure the camera preview function is correctly started or stopped
def set_preview (state):
	global camera, display_size

	if (state):
		if (camera.preview is None):
			gui_draw_message("( wait for preview )") 
			camera.start_preview(
				fullscreen = False,
				window = (0, 0, display_size[0], display_size[1]-26)  # x, y, width, height
			)
	else:
		if (camera and camera.preview):
			gui_draw_message()
			camera.stop_preview()
		timer_camera = None    # reset


def set_preview_mode (n=0):
	print "set_preview_mode"


def set_capturing (state=True):
	global capturing, gui_update, timers

	capturing = state
	# update other related variables
	if (capturing):
		timers['capturing'] = time.time()  # now in seconds since epoch
	else:
		timers['capturing'] = None
		# refresh images list as there should be updates after a capture
		load_images_list()
		# also set current image to the latest in case user wants to review it
		set_current_image(latest=True)
	# make sure GUI always reflects state
	gui_update['dirty'] = True


def capture ():
	global camera, capturing, settings, output_folder, timers

	# check timer to see if camera is ready
	if (timers['camera_ready'] is not None):
		print "timer: camera is not ready yet..."
		return

	filename = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")

	# capture a still image
	if ( settings['mode'].is_still() ):
		shots = settings['shutter_speed'].get_shots()
		print "---------\nshots: " + str(shots)
		print "   ss: " + settings['shutter_speed'].get_value(string=True, per_shot=True) + " s"
		print "  fps: " + str(camera.framerate)

		# capture the shot
		if (shots == 1):
			set_capturing(True)
			camera.capture(output_folder + filename + '.jpg', quality=100)
			set_capturing(False)
		else:
			# use a composite image to additively blend captures together
			composite = None
			capture_stream = io.BytesIO()
			streams = []
			shots_captured = 0
			set_capturing(True)
			
			# give intermediate updates
			gui_draw_capturing(shots_captured, shots)

			for foo in camera.capture_continuous(capture_stream, format='jpeg', quality=100):
				# give intermediate updates
				gui_draw_capturing(shots_captured, shots)

				# Truncate the stream to the current position (in case
				# prior iterations output a longer image)
				capture_stream.truncate()
				capture_stream.seek(0)
				# copy stream into a new stream, appended to the streams list
				temp_stream = io.BytesIO()
				temp_stream.write( capture_stream.read() )
				streams.append(temp_stream)

				# when done, save composite
				shots_captured += 1
				if (shots_captured >= shots):
					# give intermediate updates
					gui_draw_capturing(shots_captured, shots)

					# add each partial image to composite
					first_image = True
					for stream in streams:
						stream.seek(0)
						partial_capture = Image.open(stream)
						if (first_image):
							composite = partial_capture
							first_image = False
						else:
							composite = ImageChops.add(composite, partial_capture)

					composite.save(output_folder + filename + '.jpg', quality=100)
					break
			
			# clean up
			set_capturing(False)
			stream.close()
	# or capture video
	else:
		if (capturing is not True):
			set_capturing(True)
			mode_short = settings['mode'].get_value(True, True)
			
			# name comes out like this: date_480p24.h264
			camera.start_recording(output_folder + filename + '_' + mode_short + '.h264')
		else:
			camera.stop_recording()
			set_capturing(False)

	# optionally, show new-fangled capture in viewer
	if (capturing is not True and settings['review'].get_value()):
	 	set_gui_mode(3)


# returns an a pygame surface with a frame captured from camera
def get_camera_image (resize=None):
	global camera, cam_buffer_rgb, settings, timers

	img = None
	if (timers['camera_ready'] is None):
		resolution = settings['mode'].get_value()
		
		# capture into in-memory stream
		stream = io.BytesIO()
		camera.capture(stream, use_video_port=True, format='rgb')
		stream.seek(0)
		stream.readinto(cam_buffer_rgb)
		stream.close()
		img = pygame.image.frombuffer(cam_buffer_rgb[0:
			(resolution[0] * resolution[1] * 3)],
			resolution, 'RGB')

	return img


def get_camera_exposure ():
	global cam_buffer_rgb

	if (get_camera_image() is None):
		return 0

	exposure_average = 0
	for p in cam_buffer_rgb:
		exposure_average += p
	exposure_average /= len(cam_buffer_rgb)

	return (exposure_average - 127)


# --- Logic + GUI functions ----------------------------------------


def handle_input ():
	global gui_mode, capturing, display_size, do_exit, timers

	# handle timers first
	now = time.time()
	if (timers['settings']):
		if (timers['settings'] < now):
			timers['settings'] = None
			if (gui_mode == 2):
				set_gui_mode(1)
	if (timers['camera_ready']):
		if (timers['camera_ready'] < now):
			timers['camera_ready'] = None
	if (timers['camera_standby']):
		if (timers['camera_standby'] < now and capturing is not True):
			timers['camera_standby'] = None
			camera_close()
	if (timers['standby']):
		if (timers['standby'] < now and capturing is not True):
			timers['standby'] = None
			set_gui_mode(0)

	# handle event queue
	events = pygame.event.get()
	for event in events:
		# take on screen input
		# buttons 1: left, 2: middle, 3: right, 4: scroll up, 5: scroll down
		if (event.type is MOUSEBUTTONDOWN):
			# during standby
			if (gui_mode == 0):
				set_gui_mode(1)
			# left mouse click
			elif (event.button == 1):
				mousex, mousey = event.pos

				if (gui_mode == 1):
					# bottom row
					if (mousey > display_size[1]-30):
						# figure out which of the four squares was tapped
						if (mousex < display_size[0]/4):
							set_current_setting('iso')
						elif (mousex < display_size[0]/2):
							set_current_setting('shutter_speed')
						elif (mousex < 3 * display_size[0]/4):
							set_current_setting('exposure_compensation')
						else:
							set_current_setting('menu')
					# main area
					else:
						set_preview_mode(1)
				elif (gui_mode == 2):
					# main area
					if (mousey < display_size[1]-26):
						set_gui_mode(1)
					# bottom row
					else:
						# figure out place on slider as [0, 1]
						slider_position = 1.0 * (min(max(mousex, 8), display_size[0]-8) - 8) / (display_size[0]-16)
						# set current setting accordingly
						do_current_setting(position=slider_position)
				# during review
				elif (gui_mode == 3):
					if (mousex < display_size[0]/4):
						set_current_image(-1)
					elif (mousex > 3 * display_size[0]/4):
						set_current_image(1)
					else:
						set_image_active()
			# scroll mouse
			elif (event.button >= 4):
				scroll_direction = -1
				if (event.button == 5):
					scroll_direction = 1

				if (gui_mode == 3):
					set_current_image(scroll_direction)
				else:
					do_current_setting(scroll_direction)
		# else take key input
		elif (event.type is KEYDOWN):
			# exit?
			if (event.key == K_ESCAPE):
				if (gui_mode > 1):  # exit to main mode
					set_gui_mode(1)
				else:
					do_exit = True
			# other input is only handled if system is active
			# otherwise, it simply makes the system active again
			elif (gui_mode == 0):
				set_gui_mode(1)
			else:
				# central button
				if (event.key == K_DOWN):
					if (gui_mode == 1):
						capture()
					elif (gui_mode == 2):
						do_current_confirm()
					elif (gui_mode == 3):
						set_gui_mode(1)
				# left/right buttons/rotary encoder
				elif (event.key == K_LEFT):
					if (gui_mode == 3):
						set_current_image(-1)
					else:
						do_current_setting(-1)
				elif (event.key == K_RIGHT):
					if (gui_mode == 3):
						set_current_image(1)
					else:
						do_current_setting(1)
				# soft buttons (via keyboard only)
				elif (event.key == K_1):
					set_current_setting('iso')
				elif (event.key == K_2):
					set_current_setting('shutter_speed')
				elif (event.key == K_3):
					set_current_setting('exposure_compensation')
				elif (event.key == K_4):
					set_current_setting('menu')
				elif (event.key == K_0):
					set_current_setting('mode')
				# hardware buttons (on keyboard for now)
				elif (event.key == 113):  # Q
					do_exit = True
				elif (event.key == 101):  # E
					if (gui_mode == 1 or gui_mode == 2):
						set_preview_mode(1)
					elif (gui_mode == 3):
						set_image_active()
				elif (event.key == 114):  # R
				 	set_gui_mode(3)
				else:
				 	print "event.key: ", event.key

	# any input will keep standy timer active
	if (len(events) > 0):
		timers['standby'] = now + 120


# helper function to make sure operations work as intended when switching between modes
# 0: standby (display off), 1: ready for capture, 2: ready, adjust setting, 3: review
def set_gui_mode (mode=0, forced=False):
	global gui_mode, gui_update, timers

	# only do something if indeed switching to another mode
	if (mode is not gui_mode):
		now = time.time()

		if (mode == 0 or mode == 3):
			# camera is no longer needed
			set_preview(False)
			timers['camera_standby'] = now + 30

			# also clear display going into these modes
			gui_update['full'] = True
			
			# extend standby time for review (handy if taking photo took a while)
			if (mode == 3):
				timers['standby'] = now + 120
		elif ( (mode == 1 or mode == 2) and (gui_mode == 0 or gui_mode == 3) ):
			# make sure camera is active
			camera_init(restart=True, forced=forced)
			set_preview(True)
			timers['standby'] = now + 120

			# clear display (only necesary coming out of mode 3, 1 is already black)
			if (gui_mode == 3):
				gui_update['full'] = True
		
		gui_mode = mode
		gui_update['dirty'] = True


def gui_init ():
	global gui_font, screen
	
	pygame.init()
	#pygame.mouse.set_visible(False)
	gui_font = pygame.font.Font('/usr/share/fonts/truetype/droid/DroidSans.ttf', 16)
	screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)


# Draws the GUI by calling specific methods for each mode.
def gui_draw ():
	global screen, gui_update, gui_mode, capturing

	# only update display when necessary
	if (gui_update['dirty'] or capturing):
		# refresh full display
		if (gui_update['full'] is True):
			screen.fill(0)
			# on entering these modes make sure message is visible
			if (gui_mode == 1 or gui_mode == 2):
				gui_draw_message("( wait for preview )")

		# 0: mode is fine with just a display refresh
		# 1: regular use mode
		if (gui_mode == 1):
			if (capturing):
				gui_draw_capturing()
			else:
				gui_draw_bottom()
		# 2: adjust setting mode
		elif (gui_mode == 2):
			gui_draw_slider()
		# 3: review mode
		elif (gui_mode == 3):
			screen.fill(0)
			gui_draw_review()

		# update display: partial redraw only if rectangles indicated
		if (gui_update['full'] or len(gui_update['rectangles']) == 0):
			pygame.display.update()
		else:
			pygame.display.update(gui_update['rectangles'])

		# reset variables
		gui_update['dirty'] = False
		gui_update['full'] = False
		gui_update['rectangles'] = []  # clear list


# draws the GUI bottom elements
def gui_draw_bottom ():
	global screen, gui_update, gui_font, colors, current_setting, settings, display_size

	# draw background
	background_surface = pygame.Surface( (display_size[0], 26) )
	background_surface.fill(colors['black'])
	background_rect = background_surface.get_rect()
	background_rect.topleft = (0, display_size[1]-26)
	screen.blit(background_surface, background_rect)
	# add to update list
	gui_update['rectangles'].append(background_rect)

	# color the current setting square slightly different
	current_bg_surface = pygame.Surface( (display_size[0]/4, 26) )
	current_bg_surface.fill(colors['support'])
	current_bg_surface.set_alpha(150)
	current_bg_surface.convert_alpha()
	current_bg_rect = current_bg_surface.get_rect()
	for item in range(1,5):
		if ((item == 1 and current_setting == 'iso') or
			(item == 2 and current_setting == 'shutter_speed') or
			(item == 3 and current_setting == 'exposure_compensation') or
			(item == 4 and settings[current_setting].order >= 4)):
			current_bg_rect.topleft = (display_size[0]/4 * (item-1), display_size[1]-26)
	screen.blit(current_bg_surface, current_bg_rect)
	
	# iso
	isoSurfaceObj = gui_font.render('iso ' + settings['iso'].get_value(True), False, colors['white'])
	isoRectObj = isoSurfaceObj.get_rect()
	isoRectObj.topleft = (0, display_size[1]-20)
	isoRectObj.centerx = display_size[0]/8
	screen.blit(isoSurfaceObj, isoRectObj)
	# iso position
	iso_pos_surface = pygame.Surface( (settings['iso'].get_position() * display_size[0]/4, 3) )
	iso_pos_surface.fill(colors['white'])
	iso_pos_rect = iso_pos_surface.get_rect()
	iso_pos_rect.topleft = (0, display_size[1]-26)
	screen.blit(iso_pos_surface, iso_pos_rect)
	
	# shutter speed
	ssSurfaceObj = gui_font.render('ss ' + settings['shutter_speed'].get_value(True), False, colors['white'])
	ssRectObj = ssSurfaceObj.get_rect()
	ssRectObj.topleft = (0, display_size[1]-20)
	ssRectObj.centerx = 3 * display_size[0]/8
	screen.blit(ssSurfaceObj, ssRectObj)
	# shutter speed position
	ss_pos_surface = pygame.Surface( (settings['shutter_speed'].get_position() * display_size[0]/4, 3) )
	ss_pos_surface.fill(colors['white'])
	ss_pos_rect = ss_pos_surface.get_rect()
	ss_pos_rect.topleft = (display_size[0]/4, display_size[1]-26)
	screen.blit(ss_pos_surface, ss_pos_rect)
	
	# exposure
	exposure = 1.66 #get_camera_exposure()
	stop_width = display_size[0]/4 / 6

	exp_text = str(round(exposure, 1)) + ' / ' + settings['exposure_compensation'].get_value(True)
	if (exposure > 0):
		exp_text = '+' + exp_text
	exp_surf = gui_font.render(exp_text, False, colors['white'])
	exp_rect = exp_surf.get_rect()
	exp_rect.topleft = (0, display_size[1]-20)
	exp_rect.centerx = 5 * display_size[0]/8
	screen.blit(exp_surf, exp_rect)

	exp_stop_surface = pygame.Surface( (3, 5) )
	exp_stop_surface.fill(colors['white'])
	exp_stop_rect = exp_stop_surface.get_rect()
	for stop in range(-2, 3):
		exp_stop_rect.topleft = (5 * display_size[0]/8 + stop * stop_width, display_size[1]-26)
		screen.blit(exp_stop_surface, exp_stop_rect)
		if (stop == 0):
			exp_stop_rect.top = display_size[1]-23
			screen.blit(exp_stop_surface, exp_stop_rect)

	# exposure line (indicates to a max of +/- 3 stops)
	exp_pos_surface = pygame.Surface( (min(abs(exposure), 3) * stop_width, 3) )
	exp_pos_surface.fill(colors['white'])
	exp_pos_rect = exp_pos_surface.get_rect()
	if (exposure >= 0):
		exp_pos_rect.topleft  = (5 * display_size[0]/8, display_size[1]-26)
	else:
		exp_pos_rect.topright = (5 * display_size[0]/8, display_size[1]-26)
	screen.blit(exp_pos_surface, exp_pos_rect)
	
	# indicators
	## white balance:
	#WB 4500K
	## mode: still / video (480p24)
	mode_text_surf = gui_font.render(settings['mode'].get_value(True, True), False, colors['white'])
	mode_text_rect = mode_text_surf.get_rect()
	mode_text_rect.topright = (display_size[0]-50, display_size[1]-20)
	screen.blit(mode_text_surf, mode_text_rect)
	## delay: seconds
	## interval on|off
	## cam-active (cannot adjust settings?)

	gui_update['dirty'] = True


# draws visual indicator while capturing multi-exposure or video
# use phase and total variables for multi-exposures, total=0 implies video.
def gui_draw_capturing (phase=0, total=0):
	global screen, gui_update, colors, display_size, timers

	# draw background
	capture_bg_surface = pygame.Surface( (display_size[0], 26) )
	capture_bg_surface.fill(colors['black'])
	capture_bg_rect = capture_bg_surface.get_rect()
	capture_bg_rect.topleft = (0, display_size[1]-26)
	screen.blit(capture_bg_surface, capture_bg_rect)
	# add to update list
	gui_update['rectangles'].append(capture_bg_rect)

	# draw progress indicator
	progress_bg_surface = None
	if (total == 0):
		progress_bg_surface = pygame.Surface( (display_size[0], 26) )
	else:
		# width is based on progress, with a minimum for readability of text
		width = max(1.0 * phase / (total+1) * display_size[0], 100)
		progress_bg_surface = pygame.Surface( (width, 26) )		
	progress_bg_surface.fill(colors['white'])
	progress_bg_rect = progress_bg_surface.get_rect()
	progress_bg_rect.topleft = (0, display_size[1]-26)
	# add a 'recording' circle (surface, color, position, radius, width)
	pygame.draw.circle(progress_bg_surface, colors['support'], (18, 13), 10, 0)
	screen.blit(progress_bg_surface, progress_bg_rect)

	# draw a timestamp for video recordings
	timestamp_surface = None
	text = ''
	if (total == 0):
		time_passed = time.time() - timers['capturing']  # in seconds.somemore
		minutes = int(time_passed / 60)
		if (minutes < 10):
			minutes = '0' + str(minutes)
		seconds = int(time_passed % 60)
		if (seconds < 10):
			seconds = '0' + str(seconds)
		text = str(minutes) + ':' + str(seconds)
	else:
		if (phase >= total):
			text = "Processing..."
		else:
			text = str(phase+1) + ' / ' + str(total)
	timestamp_surface = gui_font.render(text, False, colors['support'])
	timestamp_rect = timestamp_surface.get_rect()
	timestamp_rect.topleft = (45, display_size[1]-22)
	screen.blit(timestamp_surface, timestamp_rect)

	# update display for intermediate display update (partial redraw for performance)
	if (total != 0):
		pygame.display.update(capture_bg_rect)

	gui_update['dirty'] = True


def gui_draw_slider ():
	global screen, gui_update, gui_font, colors, display_size

	# draw background
	slider_bg_surface = pygame.Surface( (display_size[0], 26) )
	slider_bg_surface.fill(colors['support'])
	slider_bg_rect = slider_bg_surface.get_rect()
	slider_bg_rect.topleft = (0, display_size[1]-26)
	screen.blit(slider_bg_surface, slider_bg_rect)
	# add to update list
	gui_update['rectangles'].append(slider_bg_rect)

	# draw a slider line (min width: 8px, to line up with text)
	line_surface = pygame.Surface( (get_current_position() * (display_size[0]-8) + 8, 3) )
	line_surface.fill(colors['white'])
	line_rect = line_surface.get_rect()
	line_rect.topleft = (0, display_size[1]-26)
	screen.blit(line_surface, line_rect)

	# draw setting name
	value_surface = gui_font.render(get_current_setting(True), False, colors['white'])
	value_rect = value_surface.get_rect()
	value_rect.topleft = (8, display_size[1]-20)
	screen.blit(value_surface, value_rect)

	# draw value text
	value_surface = gui_font.render(get_current_value(True), False, colors['white'])
	value_rect = value_surface.get_rect()
	value_rect.topright = (display_size[0]-8, display_size[1]-20)
	screen.blit(value_surface, value_rect)

	gui_update['dirty'] = True


# takes image from camera preview and draws it on screen
# note: currently unused
def gui_draw_camera_preview ():
	global screen, gui_update

	img = get_camera_image()
	if (img is not None):
		img = aspect_scale(img, display_size)
	
	if img is None or img.get_height() < 240:  # letterbox, clear background
		screen.fill( (50,50,50) )
	if img:
		screen.blit(img,
			((display_size[0] - img.get_width() ) / 2,
			 (display_size[1] - img.get_height()) / 2))

	gui_update['dirty'] = True


def gui_draw_review ():
	global output_folder, images, current_image, display_size

	if (len(images) == 0):
		gui_draw_message("( no images available )")
	else:
		# load image if necesary
		if (current_image['index'] != current_image['index_loaded']):
			# indicate progress
			gui_draw_message("( loading image )")

			# load image from file
			current_image['filename'] = output_folder + images[current_image['index']]
			current_image['video'] = (".h264" in current_image['filename'])

			# load only photos, not video
			if (current_image['video'] is not True):
				# open via Pillow rather than pygame to get exif data
				current_image['img_pillow'] = Image.open( current_image['filename'] )
				if (current_image['img_pillow']._getexif() is None):
					current_image['exif'] = None
				else:
					# rework exif to have human-readable keys for each value
					# exif code via: http://stackoverflow.com/a/4765242
					current_image['exif'] = {
						ExifTags.TAGS[k]: v
						for k, v in current_image['img_pillow']._getexif().items()
							if k in ExifTags.TAGS
					}
				current_image['img'] = pygame.image.load( current_image['filename'] )
			else:
				# derive framerate from filename
				regex_match = re.search('p(\d{1,2})\.', current_image['filename'])
				current_image['fps'] = int(regex_match.group(1))
			current_image['index_loaded'] = current_image['index']

		# draw current image as background
		if (current_image['video'] is not True):
			if (current_image['active']):
				pass # show only the relevant part 1:1
			else:
				# just scale to display size
				current_image['img_scaled'] = aspect_scale(current_image['img'], display_size)

			# if necessary letterbox an image that does not fit on display
			screen.blit(current_image['img_scaled'],
				((display_size[0] - current_image['img_scaled'].get_width() ) / 2,
				 (display_size[1] - current_image['img_scaled'].get_height()) / 2))
		else:
			if (current_image['active']):
				gui_draw_message("( wait for video )")
				# play a video via omxplayer
				call(['omxplayer', '--fps', str(current_image['fps']), current_image['filename'] ])
				current_image['active'] = False

			# video preview is not supported
			gui_draw_message("( tap to play video )")

		# provide info on image
		
		# draw info background
		info_bg_surface = pygame.Surface( (display_size[0], 23) )
		info_bg_surface.fill(colors['black'])
		info_bg_surface.set_alpha(127)
		info_bg_surface.convert_alpha()
		info_bg_rect = info_bg_surface.get_rect()
		info_bg_rect.topleft = (0, display_size[1]-23)
		screen.blit(info_bg_surface, info_bg_rect)

		# index / total images
		index_surface = gui_font.render('(' + str(current_image['index']+1) + ' / ' + str(len(images)) + ')', False, colors['white'])
		index_rect = index_surface.get_rect()
		index_rect.topright = (display_size[0]-8, display_size[1]-20)
		screen.blit(index_surface, index_rect)

		if (current_image['video'] is not True and current_image['exif'] is not None):
			# ISO
			iso_text = settings['iso'].get_nearby_value(0.391 * int(current_image['exif']['ISOSpeedRatings']), True)
			iso_text_surface = gui_font.render('iso ' + str(iso_text), False, colors['white'])
			iso_text_rect = iso_text_surface.get_rect()
			iso_text_rect.topleft = (0, display_size[1]-20)
			iso_text_rect.centerx = display_size[0]/8
			screen.blit(iso_text_surface, iso_text_rect)
			# ExposureTime
			ss_text = current_image['exif']['ExposureTime']
			ss_text = 1.0 * ss_text[0] / ss_text[1]
			ss_text = settings['shutter_speed'].get_nearby_value(ss_text, True)
			ss_text_surface = gui_font.render('ss ' + str(ss_text), False, colors['white'])
			ss_text_rect = ss_text_surface.get_rect()
			ss_text_rect.topleft = (0, display_size[1]-20)
			ss_text_rect.centerx = 3 * display_size[0]/8
			screen.blit(ss_text_surface, ss_text_rect)
		# Filename
		name_text_surface = gui_font.render(images[current_image['index']], False, colors['white'])
		name_text_rect = name_text_surface.get_rect()
		name_text_rect.topleft = (0, display_size[1]-20)
		name_text_rect.centerx = 3 * display_size[0]/4
		screen.blit(name_text_surface, name_text_rect)

	gui_update['full']  = True
	gui_update['dirty'] = True


# Use this to draw reusable surfaces
def gui_draw_surface (name=None, update_list=False):
	global screen, gui_update

	screen.blit(gui_surfaces[name + '_surf'], gui_surfaces[name + '_rect'])

	if (update_list):
		gui_update['rectangles'].append( gui_surfaces[name+'_rect'] )
	gui_update['dirty'] = True


# Draws message in middle of display
# note: should be called directly when state changes for immediate feedback
# @message: should be convertible to string
def gui_draw_message (message=None):
	global screen, gui_update

	# draw background
	message_bg_surface = pygame.Surface( (150, 30) )
	message_bg_surface.fill(colors['black'])
	message_bg_rect = message_bg_surface.get_rect()
	message_bg_rect.centerx = display_size[0]/2
	message_bg_rect.centery = display_size[1]/2 - 30
	screen.blit(message_bg_surface, message_bg_rect)

	# draw text to indicate preview is on, otherwise leave blank
	if (message is not None):
		state_text_surface = gui_font.render(str(message), False, colors['white'])
		state_text_rect = state_text_surface.get_rect()
		state_text_rect.centerx = display_size[0]/2
		state_text_rect.centery = display_size[1]/2 - 30
		screen.blit(state_text_surface, state_text_rect)

	# immediately update display (just affected rectangle)
	pygame.display.update(message_bg_rect)


# via: http://www.pygame.org/pcr/transform_scale/
def aspect_scale(img, (bx,by)):
	""" Scales 'img' to fit into box bx/by.
	This method will retain the original image's aspect ratio """
	ix,iy = img.get_size()
	if ix > iy:
		# fit to width
		scale_factor = bx/float(ix)
		sy = scale_factor * iy
		if sy > by:
			scale_factor = by/float(iy)
			sx = scale_factor * ix
			sy = by
		else:
			sx = bx
	else:
		# fit to height
		scale_factor = by/float(iy)
		sx = scale_factor * ix
		if sx > bx:
			scale_factor = bx/float(ix)
			sx = bx
			sy = scale_factor * iy
		else:
			sy = by

	return pygame.transform.scale(img, (int(sx), int(sy)))


# --- Main loop ---------------------------------------------


def main ():
	global do_exit

	try:
		# initialise all components
		load_images_list()
		camera_init()
		settings_init()
		gui_init()

		# get ready in right mode
		set_gui_mode(1, forced=True)
		
		# program stays in this loop unless called for exit
		while (True):
			# checking input
			handle_input()
			
			# drawing GUI
			gui_draw()

			# exit flag set?
			if (do_exit):
				break
			else:
				# pause between frames
				pygame.time.wait(50)
	except:
		# print traceback
		print "Unexpected error:"
		traceback.print_exc()
	finally:
		# cleanup
		# make sure any running systems are terminated, handlers returned, etc. on exit
		camera_close()


# with everything now defined, execute main method
main()
