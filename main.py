import math
import time
import datetime
#import picamera
#from PIL import Image, ImageChops


# --- Global variables -----------------------------------------


global camera, still_mode, preview_on, capturing
global iso, isoState, isoRange, ss, ssState, ssRange, ssDisplay, ssRangeDisplay
global white_balance, exposure_compensation, framerate

camera = None #picamera.PiCamera()
#atexit.register(camera.close)
camera.led = False  # turn LED on camera module off to avoid light leaking onto sensor

white_balance = 0  # 0 means off
exposure_compensation = 0  # 0 means not applied, can be adjusted during previews and recording
framerate = 30

isoState = 0
isoRange = [100, 200, 320, 400, 500, 640, 800]
iso = isoRange[isoState]

ssState = 0
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


# --- Utility functions ----------------------------------------


# n is -1 or +1, depending on direction of input
def setISO (n):
	global iso, isoState, isoRange
	isoState = min(max(isoState + n, 0), len(isoRange)-1)
	iso = isoRange[isoState];
	#print 'iso: ' + str(iso)


# n is -1 or +1, depending on direction of input
def setShutterSpeed (n):
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
def setExposureCompensation (n):
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
	total_snaps = int(math.ceil(ss / 1000000.0));
	per_shot_ss = ss / total_snaps
	return (total_snaps, per_shot_ss)


# Makes sure the camera preview function is correctly started or stopped
def setPreview (state):
	global camera, preview_on
	if (state):
		#if (camera.preview_state is not on):
		#	camera.start_preview()
			# make sure to give camera some time to get ready
		#	time.sleep(2)
		preview_on = True
	else:
		#if (camera.preview_state is on):
			#camera.stop_preview()
		preview_on = False


def capture ():
	global camera, iso, ss, white_balance, exposure_compensation, framerate

	filename = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")

	if (still_mode):
		shots = captures_needed(ss)
		print shots[0]

		# set up camera with correct settings
		#camera.exposure_mode = 0  # turned off
		#camera.ISO = iso
		# framerate provides upper limit for shutter speed
		# so any long captures need a lower fps to allow the camera to take more time per frame
		#camera.framerate = min(30, (shots[1] / 1000000.0))
		#camera.shutter_speed = shots[1]
		#camera.white_balance = white_balance
		#camera.exposure_compensation = exposure_compensation

		# make sure the preview is running before a capture command
		setPreview(True)

		# capture the shot
		if (shots[0] == 1):
			print "snap: " + str(shots[1] / 1000000.0) + " s"
			#camera.capture(filename + '.jpg')
		else:
			# camera.capture_sequence([
			# 	filename + '-%02d.jpg' % i
			# 	for i in range(shots[0])
			# ])
			# turn preview off before compositing to avoid wasting resources
			# during an expensive, time-consuming task
			setPreview(False)
			
			# take intermediate shots and add colour values to create composite
			# create a blank image (best filled black, which is default)
			#composite = PIL.Image.new(size=(3000,2000))
			for i in range(shots[0]):
				print "snap: " + str(shots[1] / 1000000.0) + " s"

				# add capture to composite image
				# open capture as image
				#partial_capture = PIL.Image.open(filename + '-%02d.jpg' % i)
				#composite = PIL.ImageChops.add(composite, partial_capture);

			# store composite
			# delete intermediate shots (for now, keep for testing?)
		
		# show new-fangled capture in viewer
		setPreview(False)
	else:
		# capture video
		# make sure framerate is set to something sensible, like 30 fps
		# make sure iso + ss is set to auto (for now use exp_comp to adjust?)
		# also show on display?
		pass


# --- Main control ---------------------------------------------


# Main loop
while (True):
	# testing stuff
	# for i in range(30):
	# 	setExposureCompensation(1)
	# for i in range(55):
	# 	setExposureCompensation(-1)
	# setExposureCompensation(0)

	# checking input
	
	# taking actions
	capture()

	# rendering display
	break
