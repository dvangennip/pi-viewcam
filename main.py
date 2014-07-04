import datetime
import io
import math
import os
import picamera
from PIL import Image, ImageChops
import pygame
from pygame.locals import *
import threading
import time


# Init framebuffer/touchscreen environment variables
# os.putenv('SDL_VIDEODRIVER', 'fbcon')
# os.putenv('SDL_FBDEV'      , '/dev/fb1')
# os.putenv('SDL_MOUSEDRV'   , 'TSLIB')
# os.putenv('SDL_MOUSEDEV'   , '/dev/input/touchscreen')


# --- Global variables -----------------------------------------


global camera, cam_rgb, still_mode, capturing, current_setting, settings
global framerate
global output_folder
global screen, gui_update, gui_mode, gui_font, do_exit
global timer_settings, timer_camera
global color_white, color_black, color_support

output_folder = '../DCIM/'

screen = None
gui_update = True
gui_font = None
gui_mode = 1

color_white = pygame.Color(255, 255, 255)
color_black = pygame.Color(0, 0, 0)
color_support = pygame.Color(214, 0, 50)

current_setting = 'shutter_speed'
do_exit = False
timer_settings = None
timer_camera = None  # do we have to wait before camera is ready for capture?

settings = {}
framerate = 15

capturing = False
still_mode = True

camera = None

# buffers for viewfinder data
cam_rgb = bytearray(320 * 240 * 3)


# --- Utility functions ----------------------------------------


# initiate variables and objects that are required for the main program to run
def init ():
	global camera, gui_font, gui_mode, screen, settings

	# init camera
	camera = picamera.PiCamera()
	camera.resolution = (320, 240)
	camera.vflip = True

	# init settings
	settings = {
		'menu': Setting(99, 'Menu', None, 0, [0], [0], menu=False),
		'iso': Setting(1, 'ISO', 'ISO', 1,
				[     0, 100, 200, 320, 400, 500, 640, 800],
				['auto', 100, 200, 320, 400, 500, 640, 800], menu=False),
		'shutter_speed': SettingShutter(2, 'Shutter speed', 'shutter_speed', 36,
			[0, 1/4000.0, 1/3200.0, 1/2500.0, 1/2000.0, 1/1600.0, 1/1250.0, 1/1000.0, 1/800.0, 1/640.0, 1/500.0,
				1/400.0, 1/320.0, 1/250.0, 1/200.0, 1/160.0, 1/125.0, 1/100.0, 1/80.0, 1/60.0, 1/50.0, 1/40.0,
				1/30.0, 1/25.0, 1/20.0, 1/15.0, 1/13.0, 1/10.0, 1/8.0, 1/6.0, 1/5.0, 1/4.0, 1/3.0, 1/2.5, 1/2.0,
				1/1.6, 1/1.3, 1, 1.3, 1.6, 2, 2.5, 3, 4, 5, 6, 8, 10, 13, 15],
			['auto', '1/4000', '1/3200', '1/2500', '1/2000', '1/1600', '1/1250', '1/1000', '1/800', '1/640', '1/500',
				'1/400', '1/320', '1/250', '1/200', '1/160', '1/125', '1/100', '1/80', '1/60', '1/50', '1/40',
				'1/30', '1/25', '1/20', '1/15', '1/13', '1/10', '1/8', '1/6', '1/5', '1/4', '1/3', '1/2.5', '1/2',
				'1/1.6', '1/1.3', '1', '1.3', '1.6', '2', '2.5', '3', '4', '5', '6', '8', '10', '13', '15'], menu=False),
		'exposure_compensation': Setting(3, 'Exposure compensation', 'exposure_compensation', 0, (-25,25), menu=False),
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
			'horizon']),
		'meter_mode': Setting(6, 'Metering', 'meter_mode', 0, ['average','spot','backlit','matrix']),
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
		'mode': SettingMode(8, 'Mode', 'resolution', 0, [
				[(320, 240), (2592,1944),  (1, 15), 'Still'],
				[(320, 240), (1296, 972), (24, 24), 'Video 4:3 24fps'],  # 1,42 fps
				[(320, 240), (1296, 972), (30, 30), 'Video 4:3 30fps'],
				[(320, 240), ( 640, 480), (60, 60), 'Video 4:3 480p 60fps'],  # 43,90 fps
				[(320, 240), ( 640, 480), (90, 90), 'Video 4:3 480p 90fps'],
				[(320, 180), (1296, 730), (24, 24), 'Video 16:9 720p 24fps'],  # 1,49fps
				[(320, 180), (1296, 730), (30, 30), 'Video 16:9 720p 30fps'],
				[(320, 180), (1296, 730), (48, 48), 'Video 16:9 720p 48fps'],
				[(320, 180), (1920,1080), (24, 24), 'Video 16:9 1080p 24fps'], # (partial FOV)
				[(320, 180), (1920,1080), (30, 30), 'Video 16:9 1080p 30fps']  # 1, 30
			]),
		#'delay': Setting('Shutter delay', None, 0, (0,30)),
		#'interval': Setting('Interval', None, 0, [False, True], ['off', 'on']),
		#'preview_mode': Setting('Preview mode', None, 0, [0, 1, 3], ['normal', 'histogram', 'sharpness']),
		#'review': Setting('Review after capture', None, 0, [False, True], ['off', 'on']),
		'camera_led': Setting(9, 'Camera LED', 'led', 1, [False, True], ['off', 'on']),
		#'flash': Setting('Flash', None, 0, [0, 1, 2], ['off', 'on', 'rear curtain']),
		#'power': Setting('Power', None, 1, [False, True], ['off', 'on'])
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

	# load stored settings
	#load_settings()
	
	# init the GUI
	pygame.init()
	pygame.mouse.set_visible(False)
	gui_font = pygame.font.Font('/usr/share/fonts/truetype/droid/DroidSans.ttf', 16)
	screen = pygame.display.set_mode((320,240))  #(0,0), pygame.FULLSCREEN)


def order_compare (x, y):
	global settings
	return settings[x].order - settings[y].order


# make sure any running systems are terminated, handlers returned, etc. on exit
def cleanup ():
	global camera

	# do some cleanup
	set_preview(False)
	camera.close()

	# save settings
	#save_settings()


# --- Camera + settings functions ----------------------------------------


class Setting:
	def __init__ (self, order=0, name='SettingName', name_real=None, state=0,
					in_range=[], range_display=None, restart=False, menu=True):
		self.order = order
		self.name = name
		self.name_real = name_real
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
		if (self.name_real is not None):
			preview_active = get_preview()
			if (self.cam_restart_on_apply and preview_active):
				set_preview(False)
			setattr(camera, self.name_real, self.value)
			if (self.cam_restart_on_apply and preview_active):
				set_preview(True)

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

		setattr(camera, self.name_real, self.value_per_shot)
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
		new_value = max(self.min, min(self.max, fps))

		# apply value to camera if altered
		if (self.value != new_value):
			self.value = new_value
			self.apply_value()

	def set_range (self, in_range):
		global settings
		Setting.set_range(self, in_range)
		# upon setting the new range, also get ss to stay within limits if necessary
		try:
			settings['shutter_speed'].set_state(0)
		except:
			pass


# in_range: [(tuple, preview_res), (tuple, resolution), (tuple, fps limits), 'NameString']
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

		# update preview resolution
		setattr(camera, self.name_real, self.range[self.state][0])
		# restrict framerate to current mode's limits
		# note: framerate setting may not yet be initialised, hence the try block
		try:
			settings['framerate'].set_range( self.range[self.state][2] )
		except:
			pass

	def get_value (self, string=False, preview=False):
		if (string):
			return self.range[self.state][3]  # name of mode
		elif (preview):
			return self.range[self.state][0]  # preview resolution
		else:
			return self.range[self.state][1]  # resolution

	def is_still (self):
		return (self.state == 0)


def do_settings_active (state=True):
	global gui_mode, timer_settings 

	if (state):
		set_gui_mode(2)
		# activate timer to deactive state after a delay
		timer_settings = time.time() + 10
	else:
		set_gui_mode(1)
		timer_settings = None


# confirms + deactivates the current setting
def do_current_confirm ():
	global current_setting

	# make sure main menu confirmation dives into submenu
	if (current_setting == 'menu'):
		set_current_setting(get_current_value())
	# otherwise, confirm and deactivate menu
	else:
		do_settings_active(False)


# passes on the adjustment to the currently active setting
def do_current_setting (n):
	global current_setting, settings

	do_settings_active(True)
	settings[current_setting].set_state(n)


# gets the value for the current setting
def get_current_value (string=False):
	global current_setting, settings

	return settings[current_setting].get_value(string)


def get_current_setting (name=False):
	global current_setting, settings

	if name is not True:
		return current_setting
	else:
		return settings[current_setting].get_name()


def set_current_setting (setting=None):
	global current_setting

	current_setting = setting
	do_current_setting(0)


# Makes sure the camera preview function is correctly started or stopped
def set_preview (state):
	global camera, timer_camera
	if (state):
		if (camera.previewing is not True):
			camera.start_preview()
			# make sure to give camera some time to get ready
			# instead of using wait(2), use timer to keep program from blocking
			timer_camera = time.time() + 2
	else:
		if (camera.previewing):
			camera.stop_preview()
			timer_camera = None  # reset


def get_preview ():
	global camera
	return camera.previewing


def set_capturing (state=True):
	global capturing

	if (state):
		capturing = True
	else:
		capturing = False


def capture ():
	global camera, settings, framerate, output_folder, timer_camera

	# check timer to see if there isn't a timeout for the camera
	if (timer_camera):
		print "timer: camera is not ready yet..."
		return

	filename = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")

	# set up camera
	resolution = settings['mode'].get_value()
	camera.resolution = resolution

	# make sure the preview is running before a capture command
	set_preview(True)

	if ( settings['mode'].is_still() ):
		shots = settings['shutter_speed'].get_shots() # shutter_speed
		print "---------\nshots: " + str(shots)
		print "  fps: " + str(camera.framerate)

		# capture the shot
		if (shots == 1):
			print " snap: " + settings['shutter_speed'].get_value(True) + " s"
			set_capturing(True)
			camera.capture(output_folder + filename + '.jpg', quality=100)
			set_capturing(False)
		else:
			# create a blank image (best filled black, which is default)
			composite = Image.new('RGB', size=settings['mode'].get_value())
			stream = io.BytesIO()
			shots_captured = 0
			set_capturing(True)
			
			for foo in camera.capture_continuous(stream, format='jpeg'):
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
		
		# optionally, show new-fangled capture in viewer
		# if (show_after_capture):  # some setting?
		# 	set_gui_mode(3)
	else:
		# capture video
		#set_capturing(True)
		#set_capturing(False)
		# also show on display?
		pass

	# for now, just stop preview
	set_preview(False)

	# restore cam settings to preview state
	camera.resolution = settings['mode'].get_value(preview=True)
	#camera.crop       = (0.0, 0.0, 1.0, 1.0)


# n gives direction (-1: earlier image, 1: next image)
def set_image_navigation (n=0, latest=False):
	global current_image, images, gui_update
	if (latest):
		current_image = len(images)
		gui_update = True
	elif (direction is not 0):
		current_image = min(max(current_image + n, 0), len(images))
		gui_update = True


def set_image_active (state=None):
	global current_image_active, gui_update
	if (state is None):
		current_image_active = not current_image_active
	else:
		current_image_active = state
	gui_update = True


# --- Logic + GUI functions ----------------------------------------


def handle_input ():
	global gui_mode, timer_settings, timer_camera, do_exit

	# handle timers first
	now = time.time()
	if (timer_settings):
		if (timer_settings < now):
			if (gui_mode == 2):
				set_gui_mode(1)
			timer_settings = None
	if (timer_camera):
		if (timer_camera < now):
			timer_camera = None

	# handle event queue
	for event in pygame.event.get():
		# take on screen input
		if (event.type is MOUSEBUTTONDOWN):
			mousex, mousey = event.pos

			# during standby
			if (gui_mode == 0):
				set_gui_mode(1)
			# during operation
			elif (gui_mode == 1 or gui_mode == 2):
				# bottom row
				if (mousey > 210):
					# figure out which of the four squares was tapped
					if (mousex < 80):
						set_current_setting(1)
					elif (mousex < 160):
						set_current_setting(2)
					elif (mousex < 240):
						set_current_setting(3)
					else:
						set_current_setting(0)
				# main area
				else:
					if (gui_mode == 1):
						#set_preview_mode(1)
						print "set preview mode to next"
					elif (gui_mode == 2):
						if (mousey < 70 or mousey > 150):
							set_gui_mode(1)
						else:
							# figure out place on slider as [0, 1]
							slider_position = (min(max(mousex, 20), 300) - 20) / 280
							print "slider position: " + str(position)
							# set current setting accordingly
							#do_current_setting(position=slider_position)
			# during review
			elif (gui_mode == 3):
				if (mousex < 50):
					set_image_navigation(-1)
				elif (mousex > 270):
					set_image_navigation(1)
				else:
					set_image_active()
		# else take key input
		elif (event.type is KEYDOWN):
			# soft buttons (via keyboard only)
			if (event.key == K_ESCAPE):
				do_exit = True
			elif (event.key == K_1):
				set_current_setting('iso')
			elif (event.key == K_2):
				set_current_setting('shutter_speed')
			elif (event.key == K_3):
				set_current_setting('exposure_compensation')
			elif (event.key == K_4):
				set_current_setting('menu')
			# scrollwheel
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
			# central button
			elif (event.key == K_DOWN):
				if (gui_mode == 0):
					set_gui_mode(1)
				elif (gui_mode == 1):
					capture()
				elif (gui_mode == 2):
					do_current_confirm()
				elif (gui_mode == 3):
					set_gui_mode(1)


# helper function to make sure operations work as intended when switching between modes
# 0: standby (display off), 1: ready for capture, 2: ready, adjust setting, 3: review
def set_gui_mode (mode=0):
	global gui_mode, gui_update

	if (mode is not gui_mode):
		if (mode == 0):
			set_preview(False)
		#elif (mode == 1 or mode == 2):
			# TODO turned off for now to avoid overlay
			#set_preview(True)
		elif (mode == 3):
			set_preview(False)
		gui_mode = mode
		gui_update = True


def gui_draw ():
	global screen, gui_update, gui_mode, current_setting

	# screen off
	if (gui_mode == 0 and gui_update):
		screen.fill(0)
	# regular use mode
	elif (gui_mode == 1):
		gui_draw_camera_preview()
		gui_draw_bottom()
	# adjust setting mode
	elif (gui_mode == 2):
		gui_draw_camera_preview()
		gui_draw_bottom(active=True)
		gui_draw_slider()
	# review mode
	#elif (gui_mode == 3 and gui_update):
		# draw current image as background
		# if (gui_review_zoom)
			# show only the relevant part 1:1
		# else:
			# scale to display (320x240)

	# only update display when necessary
	if (gui_update):
		pygame.display.update()
		gui_update = False


# draws the GUI bottom elements
def gui_draw_bottom (active=False):
	global screen, gui_update, gui_font, color_white, color_black, current_setting, settings

	# background squares
	for item in range(1,5):
		bg_surface = pygame.Surface( (76, 30) )
		# color the current setting square slightly differently
		if ((item == 1 and current_setting == 'iso') or
			(item == 2 and current_setting == 'shutter_speed') or
			(item == 3 and current_setting == 'exposure_compensation') or
			(item == 4 and settings[current_setting].order >= 4)):
			bg_surface.fill(color_support)
		
		if active is not True:
			bg_surface.set_alpha(150)
			bg_surface.convert_alpha()

		bg_rect = bg_surface.get_rect()
		bg_rect.topleft = (0+81*(item-1), 210)
		screen.blit(bg_surface, bg_rect)
	# iso
	isoSurfaceObj = gui_font.render('iso ' + settings['iso'].get_value(True), False, color_white)
	isoRectObj = isoSurfaceObj.get_rect()
	isoRectObj.topleft = (0, 220)
	isoRectObj.centerx = 38
	screen.blit(isoSurfaceObj, isoRectObj)
	# shutter speed
	ssSurfaceObj = gui_font.render(settings['shutter_speed'].get_value(True), False, color_white)
	ssRectObj = ssSurfaceObj.get_rect()
	ssRectObj.topleft = (0, 220)
	ssRectObj.centerx = 118
	screen.blit(ssSurfaceObj, ssRectObj)
	# exposure
	# options
	# camera ready signal

	gui_update = True


def gui_draw_slider ():
	global screen, gui_update, gui_font, color_white, color_support, current_setting

	# draw connecting element
	connector_surface = pygame.Surface( (20, 65) )
	connector_surface.fill(color_support)
	connector_rect = connector_surface.get_rect()
	square_number = 3
	if (current_setting == 'iso'):
		square_number = 0
	elif (current_setting == 'shutter_speed'):
		square_number = 1
	elif (current_setting == 'exposure_compensation'):
		square_number = 2
	connector_rect.topleft = (30 + 80*square_number, 150)  # 40-10 + 80*pos
	screen.blit(connector_surface, connector_rect)
	# draw background
	slider_bg_surface = pygame.Surface( (300, 80) )
	slider_bg_surface.fill(color_support)
	slider_bg_rect = slider_bg_surface.get_rect()
	slider_bg_rect.topleft = (10, 70)
	screen.blit(slider_bg_surface, slider_bg_rect)

	# draw a slider line for any non-menu setting
	if (current_setting is not 'menu'):
		line_surface = pygame.Surface( (280, 4) )
		line_surface.fill(color_white)
		line_rect = line_surface.get_rect()
		line_rect.topleft = (20, 125)
		screen.blit(line_surface, line_rect)

	# draw setting name
	value_surface = gui_font.render(get_current_setting(True), False, color_white)
	value_rect = value_surface.get_rect()
	value_rect.topleft = (20, 80)
	screen.blit(value_surface, value_rect)

	# draw value text
	value_surface = gui_font.render(get_current_value(True), False, color_white)
	value_rect = value_surface.get_rect()
	value_rect.topright = (300, 80)
	screen.blit(value_surface, value_rect)

	gui_update = True


# takes image from camera preview and draws it on screen
def gui_draw_camera_preview ():
	global screen, gui_update, camera, cam_rgb, settings

	img = None
	resolution = settings['mode'].get_value(preview=True)
	
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

	gui_update = True


# --- Main loop ---------------------------------------------

def main ():
	global do_exit

	init()
	
	while (True):
		# checking input
		handle_input()
		
		# drawing GUI
		gui_draw()

		# exit flag set?
		if (do_exit):
			cleanup()
			break

		# pause between frames
		pygame.time.wait(50)


# execute main loop
main()
