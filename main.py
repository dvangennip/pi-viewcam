import math
import time
import datetime
import picamera
from PIL import Image, ImageChops
import pygame
from pygame.locals import *


# --- Global variables -----------------------------------------


global camera, still_mode, preview_on, capturing, current_setting
global iso, isoState, isoRange, ss, ssState, ssRange, ssDisplay, ssRangeDisplay
global white_balance, exposure_compensation, framerate
global output_folder
global screen, gui_update, gui_mode, gui_font, do_exit
global timer_settings, timer_camera
global color_white, color_black, color_support

output_folder = '../DCIM/'

screen = None
gui_update = True
gui_font = None
set_gui_mode(1)

color_white = pygame.Color(255, 255, 255)
color_black = pygame.Color(0, 0, 0)
color_support = pygame.Color(214, 0, 50)

current_setting = 2  # shutter speed
do_exit = False
timer_settings = None
timer_camera = None  # do we have to wait before camera is ready for capture?

white_balance = 'auto'  # off|auto (see picamera/camera.py AWB_MODES)
exposure_compensation = 0  # 0 means not applied, can be adjusted during previews and recording
framerate = 15

isoState = 0
isoRange = [100, 200, 320, 400, 500, 640, 800]
iso = isoRange[isoState]

ssState = 35
ssRange = [1/4000.0, 1/3200.0, 1/2500.0, 1/2000.0, 1/1600.0, 1/1250.0, 1/1000.0, 1/800.0, 1/640.0, 1/500.0,
			1/400.0, 1/320.0, 1/250.0, 1/200.0, 1/160.0, 1/125.0, 1/100.0, 1/80.0, 1/60.0, 1/50.0, 1/40.0,
			1/30.0, 1/25.0, 1/20.0, 1/15.0, 1/13.0, 1/10.0, 1/8.0, 1/6.0, 1/5.0, 1/4.0, 1/3.0, 1/2.5, 1/2.0,
			1/1.6, 1/1.3, 1, 1.3, 1.6, 2, 2.5, 3, 4, 5, 6, 8, 10, 13, 15]
ssRangeDisplay = ['1/4000', '1/3200', '1/2500', '1/2000', '1/1600', '1/1250', '1/1000', '1/800', '1/640', '1/500',
			'1/400', '1/320', '1/250', '1/200', '1/160', '1/125', '1/100', '1/80', '1/60', '1/50', '1/40',
			'1/30', '1/25', '1/20', '1/15', '1/13', '1/10', '1/8', '1/6', '1/5', '1/4', '1/3', '1/2.5', '1/2',
			'1/1.6', '1/1.3', '1', '1.3', '1.6', '2', '2.5', '3', '4', '5', '6', '8', '10', '13', '15']
ssDisplay = ssRangeDisplay[ssState]
ss = ssRange[ssState]  # shutter speed in microseconds

preview_on = False
capturing = False
still_mode = True

camera = None


# --- Utility functions ----------------------------------------


# initiate variables and objects that are required for the main program to run
def init ():
	global camera, gui_font, gui_mode, screen

	# init camera
	camera = picamera.PiCamera()
	#camera.led = False  # turn LED on camera module off to avoid light leaking onto sensor

	# init settings
	set_iso(0)
	set_exposure_compensation(0)
	set_shutter_speed(0)
	
	# init the GUI
	pygame.init()
	pygame.mouse.set_visible(False)
	gui_font = pygame.font.Font('/usr/share/fonts/truetype/droid/DroidSans.ttf', 16)
	screen = pygame.display.set_mode((320,240))  #(0,0), pygame.FULLSCREEN)


# make sure any running systems are terminated, handlers returned, etc. on exit
def cleanup ():
	global camera

	# do some cleanup
	set_preview(False)
	camera.close()


# --- Camera + settings functions ----------------------------------------


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
	do_settings_active(False)


# passes on the adjustment to the currently active setting
def do_current_setting (n):
	global current_setting

	do_settings_active(True)

	if current_setting == 1:  # iso
		set_iso(n)
	elif current_setting == 2:  # shutter_speed
		set_shutter_speed(n)
	elif current_setting == 3:  # exposure_compensation
		set_exposure_compensation(n)


# gets the value for the current setting
def get_current_value (string=True):
	global current_setting

	if current_setting == 1:
		if string:
			return str(get_iso())
		else:
			return get_iso()
	elif current_setting == 2:
		if string:
			return str(get_shutter_speed(True))
		else:
			return get_shutter_speed()
	elif current_setting == 3:
		if string:
			return str(get_exposure_compensation())
		else:
			return get_exposure_compensation()


def get_current_setting (string=False):
	global current_setting

	if string is not True:
		return current_setting
	else:
		# TODO dict/array thingy
		return 'SettingName'


def set_current_setting (setting=None):
	global current_setting, gui_mode

	if (setting == None):
		TypeError, "setting must be specified."
	else:
		current_setting = setting
		do_current_setting(0)


def get_iso ():
	global iso
	return iso

# n is -1 or +1, depending on direction of input
def set_iso (n=0):
	global iso, isoState, isoRange
	isoState = min(max(isoState + n, 0), len(isoRange)-1)
	iso = isoRange[isoState];
	#print 'iso: ' + str(iso)


def get_shutter_speed (forDisplay=False):
	global ss, ssDisplay
	if (forDisplay):
		return ssDisplay
	else:
		return ss


# n is -1 or +1, depending on direction of input
def set_shutter_speed (n=0):
	global ss, ssState, ssDisplay, ssRange, ssRangeDisplay
	ssState = max(ssState + n, 0)

	# ss gets values from predefined array or, if it exceeds that, incremental values
	if (ssState > len(ssRange)-1):
		# add or subtract 5 seconds per tick
		# this is in principle infinite (no upper limits)
		ssDisplay = 15 + (ssState - len(ssRange)+1) * 5
		ss = ssDisplay * 1000000    #convert to microseconds

		# make display for anything over a minute a little nicer
		if (ssDisplay >= 60):
			ssSeconds = ssDisplay % 60
			if (ssSeconds < 10):
				ssSeconds = '0' + str(ssSeconds)
			ssDisplay = str(ssDisplay / 60) + 'm' + str(ssSeconds) 
	else:
		# take values from array
		ss = int(ssRange[ssState] * 1000000)  #convert to microseconds
		ssDisplay = ssRangeDisplay[ssState]
	#print 'ss: ' + str(ssDisplay) + ' / ' + str(ss)


def get_exposure_compensation ():
	global exposure_compensation
	return exposure_compensation


# n is -1 or +1, depending on direction of input
# if n = 0, exposure compensation will be reset to 0
def set_exposure_compensation (n=0):
	global exposure_compensation
	if (n == 0):
		exposure_compensation = 0
	else:
		exposure_compensation = min(max(exposure_compensation + n, -25), 25)
	#print exposure_compensation


# RaspiCam only supports shutter speeds up to 1 second.
# longer exposures thus need be composites of several shots in rapid succession.
# returns number of captures needed [0], and shutter speed per capture [1]
def captures_needed (ss):
	total_snaps = int(math.ceil(ss / 1000000.0))
	per_shot_ss = ss / total_snaps
	return (total_snaps, per_shot_ss)


# Makes sure the camera preview function is correctly started or stopped
def set_preview (state):
	global camera, preview_on, timer_camera
	if (state):
		if (camera.previewing is not True):
			camera.start_preview()
			# make sure to give camera some time to get ready
			timer_camera = time.time() + 2
		preview_on = True
	else:
		if (camera.previewing):
			camera.stop_preview()
			timer_camera = None  # reset
		preview_on = False


# adjusts preview mode
# 0: default, 1: live histogram, 2: sharpness
def set_preview_mode (n=0):
	global preview_mode
	preview_mode = min(max(preview_mode + n, 0), 2)


def set_capturing (state=True):
	global capturing

	if (state):
		capturing = True
	else:
		capturing = False


def capture ():
	global camera, iso, ss, white_balance, exposure_compensation, framerate
	global ssDisplay, output_folder, timer_camera

	# check timer to see if there isn't a timeout for the camera
	if (timer_camera):
		print "camera is not ready yet"
		return

	filename = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")

	if (still_mode):
		shots = captures_needed(ss)
		print shots[0]

		# set up camera with correct settings
		# framerate provides upper limit for shutter speed
		# so any long captures need a lower fps to allow the camera to take more time per frame
		camera.framerate = min(15, (shots[1] / 1000000.0))  # 15fps is max for high res capture
		camera.shutter_speed = int(shots[1])
		camera.ISO = iso
		camera.white_balance = white_balance
		camera.exposure_compensation = exposure_compensation
		camera.resolution = (2592,1944)

		# make sure the preview is running before a capture command
		set_preview(True)

		# capture the shot
		if (shots[0] == 1):
			print "snap: " + ssDisplay + " s"
			set_capturing(True)
			camera.capture(output_folder + filename + '.jpg', quality=100)
			set_capturing(False)
		else:
			set_capturing(True)
			camera.capture_sequence([
			 	output_folder + filename + '-%02d.jpg' % i
			 	for i in range(shots[0])
			 ])
			set_capturing(True)

			# turn preview off before compositing to avoid wasting resources
			# during an expensive, time-consuming task
			set_preview(False)
			
			# take intermediate shots and add colour values to create composite
			# create a blank image (best filled black, which is default)
			composite = Image.new('RGB', size=(2592,1944))
			for i in range(shots[0]):
				print "snap: " + str(shots[1] / 1000000.0) + " s"

				# add capture to composite image
				# open capture as image
				try:
					partial_capture = Image.open(output_folder + filename + '-%02d.jpg' % i)
					composite = ImageChops.add(composite, partial_capture);
				except:
					print "partial capture not found: " + output_folder + filename + '-%02d.jpg' % i

			# store composite
			composite.save(output_folder + filename + '.jpg', quality=100)
			# delete intermediate shots (for now, keep for testing?)
		
		# optionally, show new-fangled capture in viewer
		# if (show_after_capture):
		# 	set_gui_mode(3)
		# for now, just stop preview
		set_preview(False)
	else:
		# capture video
		# make sure framerate is set to something sensible, like 30 fps
		# make sure iso + ss is set to auto (for now use exp_comp to adjust?)
		# also show on display?
		pass


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
	global gui_mode, timer_settings, timer_camera

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
						set_current_setting(4)
				# main area
				else:
					if (gui_mode == 1):
						set_preview_mode(1)
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
				set_current_setting(1)
			elif (event.key == K_2):
				set_current_setting(2)
			elif (event.key == K_3):
				set_current_setting(3)
			elif (event.key == K_4):
				set_current_setting(4)
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
	global screen, gui_update, gui_font, color_white, color_black, current_setting

	# background squares
	for item in range(1,5):
		bg_surface = pygame.Surface( (76, 30) )
		# color the current setting square slightly differently
		if (item == current_setting or (item >= 4 and current_setting >= 4)):
			bg_surface.fill(color_support)
		
		if active is not True:
			bg_surface.set_alpha(150)
			bg_surface.convert_alpha()

		bg_rect = bg_surface.get_rect()
		bg_rect.topleft = (0+80*(item-1), 210)
		screen.blit(bg_surface, bg_rect)
	# iso
	isoSurfaceObj = gui_font.render('iso ' + str(get_iso()), False, color_white)
	isoRectObj = isoSurfaceObj.get_rect()
	isoRectObj.topleft = (0, 220)
	isoRectObj.centerx = 38
	screen.blit(isoSurfaceObj, isoRectObj)
	# shutter speed
	ssSurfaceObj = gui_font.render(get_shutter_speed(True), False, color_white)
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
	connector_rect.topleft = (30 + 80*min(current_setting-1, 3), 150)  # 40-10 + 80*pos
	screen.blit(connector_surface, connector_rect)
	# draw background
	slider_bg_surface = pygame.Surface( (300, 80) )
	slider_bg_surface.fill(color_support)
	slider_bg_rect = slider_bg_surface.get_rect()
	slider_bg_rect.topleft = (10, 70)
	screen.blit(slider_bg_surface, slider_bg_rect)

	# draw a slider line for any non-menu setting
	if (current_setting is not 4):
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
	value_surface = gui_font.render(get_current_value(), False, color_white)
	value_rect = value_surface.get_rect()
	value_rect.topright = (300, 80)
	screen.blit(value_surface, value_rect)

	gui_update = True


# takes image from camera preview and draws it on screen
def gui_draw_camera_preview ():
	global camera, screen, gui_update

	screen.fill( (50, 50, 50) )  # just clear background for now
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


# execute main loop
main()
