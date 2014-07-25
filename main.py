import datetime
import io
import math
import os
import picamera
from PIL import Image, ImageChops
import pygame
from pygame.locals import *
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


global camera, cam_rgb, capturing, current_setting, settings, timers, do_exit
global output_folder
global screen, gui_update, gui_mode, gui_font, colors, display_size

output_folder = '../DCIM/'

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

# buffers for viewfinder data
cam_rgb = bytearray(320 * 240 * 3)


# --- Settings functions ----------------------------------------


# initiate all program and camera settings
def settings_init ():
	global settings

	settings = {
		'menu': Setting(99, 'Menu', None, 0, [0], [0], menu=False),
		'iso': Setting(1, 'ISO', 'ISO', 1,
				[     0, 100, 200, 320, 400, 500, 640, 800],
				['auto', 100, 200, 320, 400, 500, 640, 800],
				menu=False, exif='EXIF.ISOSpeedRatings'),
		'shutter_speed': SettingShutter(2, 'Shutter speed', 'shutter_speed', 36,
			[0, 1/4000.0, 1/3200.0, 1/2500.0, 1/2000.0, 1/1600.0, 1/1250.0, 1/1000.0, 1/800.0, 1/640.0, 1/500.0,
				1/400.0, 1/320.0, 1/250.0, 1/200.0, 1/160.0, 1/125.0, 1/100.0, 1/80.0, 1/60.0, 1/50.0, 1/40.0,
				1/30.0, 1/25.0, 1/20.0, 1/15.0, 1/13.0, 1/10.0, 1/8.0, 1/6.0, 1/5.0, 1/4.0, 1/3.0, 1/2.5, 1/2.0,
				1/1.6, 1/1.3, 1, 1.3, 1.6, 2, 2.5, 3, 4, 5, 6, 8, 10, 13, 15],
			['auto', '1/4000', '1/3200', '1/2500', '1/2000', '1/1600', '1/1250', '1/1000', '1/800', '1/640', '1/500',
				'1/400', '1/320', '1/250', '1/200', '1/160', '1/125', '1/100', '1/80', '1/60', '1/50', '1/40',
				'1/30', '1/25', '1/20', '1/15', '1/13', '1/10', '1/8', '1/6', '1/5', '1/4', '1/3', '1/2.5', '1/2',
				'1/1.6', '1/1.3', '1', '1.3', '1.6', '2', '2.5', '3', '4', '5', '6', '8', '10', '13', '15'],
				menu=False, exif='EXIF.ShutterSpeedValue'),
		'exposure_compensation': Setting(3, 'Exposure compensation', 'exposure_compensation', 0, (-25,25),
			menu=False, exif='EXIF.ExposureBias'),
		'framerate': SettingFramerate(4, 'Framerate', 'framerate', 15, (1,15), restart=True, menu=False),
		'awb_mode': Setting(5, 'White balance', 'awb_mode', 1, [
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
		'meter_mode': Setting(6, 'Metering', 'meter_mode', 0, ['average','spot','backlit','matrix'],
			exif='EXIF.MeteringMode'),
		# Image effect list below is taken from camera.IMAGE_EFFECTS minus several
		# that cause trouble or have no effect
		'image_effect': Setting(7, 'Image effect', 'image_effect', 0, [
			'none',
			'negative',
			'solarize',
			#'posterize',
			#'whiteboard',
			#'blackboard',
			'sketch',
			'denoise',
			'emboss',
			'oilpaint',
			'hatch',
			'gpen',
			'pastel',
			'watercolor',
			'film',
			'blur',
			#'saturation',
			'colorswap',
			'washedout',
			'posterise',
			#'colorpoint',
			#'colorbalance',
			'cartoon']),
		'sharpness':  Setting( 8, 'Sharpness',  'sharpness',   0, (-100,100), exif='EXIF.Sharpness'),
		'contrast':   Setting( 9, 'Contrast',   'contrast',    0, (-100,100), exif='EXIF.Contrast'),
		'brightness': Setting(10, 'Brightness', 'brightness', 50, (0,100), exif='EXIF.BrightnessValue'),
		'saturation': Setting(11, 'Saturation', 'saturation',  0, (-100,100), exif='EXIF.Saturation'),
		'vflip': Setting(20, 'Flip image vertically',   'vflip', 1, [False, True], ['off', 'on']),
		'hflip': Setting(21, 'Flip image horizontally', 'hflip', 0, [False, True], ['off', 'on']),
		'mode': SettingMode(96, 'Mode', 'resolution', 0, [
				[(2592,1944),  (1, 15), 'Still'],
				[(1296, 972), (24, 24), 'Video 4:3 24fps'],  # 1,42 fps
				[(1296, 972), (30, 30), 'Video 4:3 30fps'],
				[( 640, 480), (60, 60), 'Video 4:3 480p 60fps'],  # 43,90 fps
				[( 640, 480), (90, 90), 'Video 4:3 480p 90fps'],
				[(1296, 730), (24, 24), 'Video 16:9 720p 24fps'],  # 1,49fps
				[(1296, 730), (30, 30), 'Video 16:9 720p 30fps'],
				[(1296, 730), (48, 48), 'Video 16:9 720p 48fps'],
				[(1920,1080), (24, 24), 'Video 16:9 1080p 24fps'], # (partial FOV)
				[(1920,1080), (30, 30), 'Video 16:9 1080p 30fps']  # 1, 30
			]),
		#'delay': Setting(30, 'Shutter delay', None, 0, (0,30)),
		#'interval': Setting(31, 'Interval', None, 0, [False, True], ['off', 'on']),
		#'preview_mode': Setting(40, 'Preview mode', None, 0, [0, 1, 3], ['normal', 'histogram', 'sharpness']),
		'review': Setting(41, 'Review after capture', None, 0, [False, True], ['off', 'on']),
		'camera_led': Setting(97, 'Camera LED', 'led', 1, [False, True], ['off', 'on']),
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
					in_range=[], range_display=None, restart=False, menu=True, exif=None):
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
		self.cam_restart_on_apply = restart
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
			if (self.value != getattr(camera, self.name_real)):
				setattr(camera, self.name_real, self.value)

		if (self.exif is not None):
			camera.exif_tags[self.exif] = str(self.value)

		# if (self.name_real == 'ISO'):
		# 	print "ISO      setting: ", self.value
		# 	print "ISO  analog gain: ", 1.0 * camera.analog_gain
		# 	print "ISO digital gain: ", 1.0 * camera.digital_gain

	# only set value directly when known to be valid (no checking is done)
	def set_value (self, value):
		self.value = value
		self.apply_value()

	def get_value (self, string=False):
		if (string):
			# continuous value
			if (self.range is None):
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

		# RaspiCam only supports shutter speeds up to 1 second.
		# longer exposures thus need be composites of several shots in rapid succession.
		if (self.value < 1000000):
			self.value_per_shot  = self.value
			self.number_of_shots = 1
		else:
			self.number_of_shots = int(math.ceil(self.value / 1000000.0))
			self.value_per_shot  = self.value / self.number_of_shots

		# apply value to camera
		self.apply_value()

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
		global settings

		# update camera resolution
		setattr(camera, self.name_real, self.range[self.state][0])
		# restrict framerate to current mode's limits
		# note: framerate setting may not yet be initialised, hence the try block
		try:
			settings['framerate'].set_range( self.range[self.state][1] )
		except:
			pass

	def get_value (self, string=False):
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
def do_current_setting (n):
	global current_setting, settings, gui_update

	do_settings_active(True)
	settings[current_setting].set_state(n)
	# make sure any changes are reflected on screen
	gui_update['dirty'] = True


# gets the value for the current setting
def get_current_value (string=False):
	global current_setting, settings
	return settings[current_setting].get_value(string)


def get_current_position ():
	global current_setting, settings
	return settings[current_setting].get_position()


# --- Image navigation functions ----------------------------------------


# n gives direction (-1: earlier image, 1: next image)
def set_image_navigation (n=0, latest=False):
	global current_image, images, gui_update
	if (latest):
		current_image = len(images)
		gui_update['dirty'] = True
	elif (direction is not 0):
		current_image = min(max(current_image + n, 0), len(images))
		gui_update['dirty'] = True


def set_image_active (state=None):
	global current_image_active, gui_update
	if (state is None):
		current_image_active = not current_image_active
	else:
		current_image_active = state
	gui_update['dirty'] = True


# --- Camera functions ----------------------------------------


# @restart: can be used to re-init the camera after it was terminated
def camera_init (restart=False, forced=False):
	global camera, settings, display_size, timers

	timers['camera_standby'] = None  # reset

	if (camera is None or camera.closed is True):
		camera = picamera.PiCamera()
		camera.preview_fullscreen = False
		camera.preview_window = (0, 0, display_size[0], display_size[1]-26)  # x, y, width, height
		
	# re-apply all values to the new, set-to-defaults camera object
	if (restart or forced):
		for key in settings:
			settings[key].apply_value()
		
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
	global camera

	if (state):
		if (camera.previewing is not True):
			camera.start_preview()
	else:
		if (camera.previewing is True):
			camera.stop_preview()
		timer_camera = None    # reset


def set_capturing (state=True):
	global capturing, gui_update, timers

	capturing = state
	# update other related variables
	if (capturing):
		timers['capturing'] = time.time()  # now in seconds since epoch
	else:
		timers['capturing'] = None
	# make sure GUI always reflects state
	gui_update['dirty'] = True


def capture ():
	global camera, capturing, settings, output_folder, timers

	# check timer to see if there isn't a timeout for the camera
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
			# create a blank image (best filled black, which is default)
			composite = Image.new('RGB', size=settings['mode'].get_value())
			stream = io.BytesIO()
			shots_captured = 0
			set_capturing(True)
			
			# give intermediate updates
			gui_draw_capturing(0, shots)

			for foo in camera.capture_continuous(stream, format='jpeg', quality=100):
				# give intermediate updates
				gui_draw_capturing(shots_captured, shots)

				# Truncate the stream to the current position (in case
				# prior iterations output a longer image)
				stream.truncate()
				stream.seek(0)
				partial_capture = Image.open(stream)
				composite = ImageChops.add(composite, partial_capture)

				# when done, save composite
				shots_captured += 1
				if (shots_captured >= shots):
					composite.save(output_folder + filename + '.jpg', quality=100)
					break
			
			# clean up
			set_capturing(False)
			stream.close()
	# or capture video
	else:
		if (capturing is not True):
			set_capturing(True)
			fps = settings['framerate'].get_value(True)
			camera.start_recording(output_folder + filename + '_' + fps + 'fps.h264')
		else:
			camera.stop_recording()
			set_capturing(False)

	# optionally, show new-fangled capture in viewer
	if (capturing is not True and settings['review'].get_value()):
	 	set_gui_mode(3)


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
		if (event.type is MOUSEBUTTONDOWN):
			mousex, mousey = event.pos

			# during standby
			if (gui_mode == 0):
				set_gui_mode(1)
			# during operation
			elif (gui_mode == 1):
				# bottom row
				if (mousey > display_size[1]-30):
					# figure out which of the four squares was tapped
					if (mousex < display_size[0]/4):
						set_current_setting(1)
					elif (mousex < display_size[0]/2):
						set_current_setting(2)
					elif (mousex < 3 * display_size[0]/4):
						set_current_setting(3)
					else:
						set_current_setting(0)
				# main area
				else:
					#set_preview_mode(1)
					print "set preview mode to next"
			elif (gui_mode == 2):
				# main area
				if (mousey < display_size[1]-26):
					set_gui_mode(1)
				# bottom row
				else:
					# figure out place on slider as [0, 1]
					slider_position = (min(max(mousex, 10), display_size[0]-10) - 10) / display_size[0]-20
					print "slider position: " + str(position)
					# set current setting accordingly
					#do_current_setting(position=slider_position)
			# during review
			elif (gui_mode == 3):
				if (mousex < display_size[0]/4):
					set_image_navigation(-1)
				elif (mousex > 3 * display_size[0]/4):
					set_image_navigation(1)
				else:
					set_image_active()
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
						set_image_navigation(-1)
					else:
						do_current_setting(-1)
				elif (event.key == K_RIGHT):
					if (gui_mode == 3):
						set_image_navigation(1)
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

	# any input will keep standy timer active
	if (len(events) > 0):
		timers['standby'] = now + 40


# helper function to make sure operations work as intended when switching between modes
# 0: standby (display off), 1: ready for capture, 2: ready, adjust setting, 3: review
def set_gui_mode (mode=0, forced=False):
	global gui_mode, gui_update, timers

	# only do something if indeed switching to another mode
	if (mode is not gui_mode):
		if (mode == 0 or mode == 3):
			# camera is no longer needed
			set_preview(False)
			timers['camera_standby'] = time.time() + 30

			# also clear display going into these modes
			gui_update['full'] = True
			
			# extend standby time for review (handy if taking photo took a while)
			if (mode == 3):
				timers['standby'] = time.time() + 40
		elif ( (mode == 1 or mode == 2) and (gui_mode == 0 or gui_mode == 3) ):
			# make sure camera is active
			camera_init(restart=True, forced=forced)
			set_preview(True)
			timers['standby'] = time.time() + 40

			# clear display (only necesary coming out of mode 3, 1 is already black)
			if (gui_mode == 3):
				gui_update['full'] = True
		
		gui_mode = mode
		gui_update['dirty'] = True


def gui_init ():
	global gui_font, screen
	
	pygame.init()
	pygame.mouse.set_visible(False)
	gui_font = pygame.font.Font('/usr/share/fonts/truetype/droid/DroidSans.ttf', 16)
	screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)


# Draws the GUI by calling specific methods for each mode.
def gui_draw ():
	global screen, gui_update, gui_mode, capturing

	# only update display when necessary
	if (gui_update['dirty'] or capturing):
		# screen off
		if (gui_mode == 0):
			screen.fill(0)
		# regular use mode
		elif (gui_mode == 1):
			if (capturing):
				gui_draw_capturing()
			else:
				gui_draw_bottom()
		# adjust setting mode
		elif (gui_mode == 2):
			gui_draw_slider()
		# review mode
		elif (gui_mode == 3):
			screen.fill(100)  # temporary indicator of mode 3
			# draw current image as background
			# if (gui_review_zoom)
				# show only the relevant part 1:1
			# else:
				# scale to display (320x240)

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
def gui_draw_bottom (active=False):
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
	# shutter speed
	ssSurfaceObj = gui_font.render(settings['shutter_speed'].get_value(True), False, colors['white'])
	ssRectObj = ssSurfaceObj.get_rect()
	ssRectObj.topleft = (0, display_size[1]-20)
	ssRectObj.centerx = 3 * display_size[0]/8
	screen.blit(ssSurfaceObj, ssRectObj)
	# exposure
	# options
	# camera ready signal

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
		width = max(1.0 * phase / total * display_size[0], 100)
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
	slider_bg_surface = pygame.Surface( (display_size[0], 23) )
	slider_bg_surface.fill(colors['support'])
	slider_bg_rect = slider_bg_surface.get_rect()
	slider_bg_rect.topleft = (0, display_size[1]-23)
	screen.blit(slider_bg_surface, slider_bg_rect)
	# add to update list
	gui_update['rectangles'].append(slider_bg_rect)

	# draw a slider line
	line_surface = pygame.Surface( (display_size[0], 3) )
	line_surface.fill(colors['white'])
	line_rect = line_surface.get_rect()
	line_rect.topleft = (0, display_size[1]-26)
	screen.blit(line_surface, line_rect)
	# add to update list
	gui_update['rectangles'].append(line_rect)

	# draw slider position indicator
	indicator_surface = pygame.Surface( (6, 26) )
	indicator_surface.fill(colors['black'])
	indicator_rect = indicator_surface.get_rect()
	indicator_pos = get_current_position() * (display_size[0] - 22) + 8  # 2 * margin + width
	indicator_rect.topleft = (indicator_pos, display_size[1]-26)
	screen.blit(indicator_surface, indicator_rect)

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
	global screen, gui_update, camera, cam_rgb, settings

	img = None
	resolution = settings['mode'].get_value()
	
	# capture into in-memory stream
	stream = io.BytesIO()
	camera.capture(stream, use_video_port=True, format='rgb')
	stream.seek(0)
	stream.readinto(cam_rgb)  # stream -> YUV buffer
	stream.close()
	img = pygame.image.frombuffer(cam_rgb[0:
		(resolution[0] * resolution[1] * 3)],
		resolution, 'RGB')

	if img is None or img.get_height() < 240:  # letterbox, clear background
		screen.fill( (50,50,50) )
	if img:
		screen.blit(img,
			((320 - img.get_width() ) / 2,
			(240 - img.get_height()) / 2))

	gui_update['dirty'] = True


# --- Main loop ---------------------------------------------


def main ():
	global do_exit

	try:
		# initialise all components
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
