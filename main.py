import math
import time
import datetime
import picamera
from PIL import Image, ImageChops
import pygame
from pygame.locals import *


# --- Global variables -----------------------------------------


global camera, still_mode, preview_on, capturing, current_setting, settings_mode
global iso, isoState, isoRange, ss, ssState, ssRange, ssDisplay, ssRangeDisplay
global white_balance, exposure_compensation, framerate
global output_folder, do_exit

output_folder = '../DCIM/'

settings_mode = False
current_setting = 'shutter_speed'
do_exit = False

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

camera = picamera.PiCamera()
#camera.led = False  # turn LED on camera module off to avoid light leaking onto sensor


# --- Utility functions ----------------------------------------


def do_settings_active (state=True):
	global settings_mode

	if (state):
		settings_mode = True
		# activate timer to return to false/deactive state
	else:
		settings_mode = False


# confirms + deactivates the current setting
def do_current_confirm ():
	do_settings_active(False)


# passes on the adjustment to the currently active setting
def do_current_setting (n):
	global current_setting

	do_settings_active(True)

	if current_setting == 'iso':
		set_iso(n)
	elif current_setting == 'shutter_speed':
		set_shutter_speed(n)
	elif current_setting == 'exposure_compensation':
		set_exposure_compensation(n)


# gets the value for the current setting
def get_current_setting ():
	global current_setting

	if current_setting == 'iso':
		return str(get_iso())
	elif current_setting == 'shutter_speed':
		return str(get_shutter_speed(True))
	elif current_setting == 'exposure_compensation':
		return str(get_exposure_compensation())


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
	global camera, preview_on
	if (state):
		if (camera.previewing is not True):
			camera.start_preview()
			# make sure to give camera some time to get ready
			time.sleep(2)
		preview_on = True
	else:
		if (camera.previewing):
			camera.stop_preview()
		preview_on = False


def capture ():
	global camera, iso, ss, white_balance, exposure_compensation, framerate
	global ssDisplay 
	global output_folder

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
			camera.capture(output_folder + filename + '.jpg', quality=100)
		else:
			camera.capture_sequence([
			 	output_folder + filename + '-%02d.jpg' % i
			 	for i in range(shots[0])
			 ])
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
		
		# show new-fangled capture in viewer
		set_preview(False)
	else:
		# capture video
		# make sure framerate is set to something sensible, like 30 fps
		# make sure iso + ss is set to auto (for now use exp_comp to adjust?)
		# also show on display?
		pass


# --- Main control ---------------------------------------------


# Main loop
def __main__ ():
	global settings_mode, do_exit

	# init settings
	set_iso(0)
	set_exposure_compensation(0)
	set_shutter_speed(0)
	
	# start the GUI
	pygame.init()
	pygame.mouse.set_visible(False)
	fontObj = pygame.font.Font('/usr/share/fonts/truetype/droid/DroidSans.ttf', 14)
	whiteColor = pygame.Color(255, 255, 255)
	screen = pygame.display.set_mode((320,240))  #(0,0), pygame.FULLSCREEN)

	while (True):
		# checking input
		for event in pygame.event.get():
			# take on screen input
			if (event.type is MOUSEBUTTONDOWN):
				mousex, mousey = event.pos
			# else take key input
			elif (event.type is KEYDOWN):
				if (event.key == K_ESCAPE):
					do_exit = True
				elif (event.key == K_LEFT):
					do_current_setting(-1)
				elif (event.key == K_RIGHT):
					do_current_setting(1)
				elif (event.key == pygame.K_SPACE or event.key == K_DOWN):
					if (settings_mode):
						do_current_confirm()
					else:
						# dirty hack to show something is happening...
						screen.fill(155)  # blue?
						pygame.display.update()
						capture()
		
		# drawing GUI
		screen.fill(0)  # clear background

		msgSurfaceObj = fontObj.render(current_setting + ': ' +get_current_setting(), False, whiteColor)
		msgRectObj = msgSurfaceObj.get_rect()
		msgRectObj.topleft = (10, 20)
		screen.blit(msgSurfaceObj, msgRectObj)

		# updating display
		pygame.display.update()

		# exit?
		if (do_exit):
			break

# execute main loop
__main__()

# do some cleanup
set_preview(False)
camera.close()
