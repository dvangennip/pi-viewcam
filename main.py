import math
import datetime
#import picamera
#from PIL import Image, ImageChops


# --- Global variables -----------------------------------------


global camera, iso, shutter_speed, white_balance, exposure_compensation
global still_mode, active, capturing

camera = None #picamera.PiCamera()
#atexit.register(camera.close)
iso = 100
shutter_speed = 1400000  # in microseconds
exposure_compensation = 0  # 0 means not applied, can be adjusted during previews and recording

isoState = 0
isoRange = [100, 200, 320, 400, 500, 640, 800]
ssState = 0
ssRange = [1/4000, 1/3200, 1/2500, 1/2000, 1/1600, 1/1250, 1/1000, 1/800, 1/640, 1/500,
			1/400, 1/320, 1/250, 1/200, 1/160, 1/125, 1/100, 1/80, 1/60, 1/50, 1/40,
			1/30, 1/25, 1/20, 1/15, 1/13, 1/10, 1/8, 1/6, 1/5, 1/4, 1/3, 1/2.5, 1/2,
			1/1.6, 1/1.3, 1, 1.3, 1.6, 2, 2.5, 3, 4, 5, 6, 8, 10, 13, 15, 20, 25, 30]

active = False
capturing = False
still_mode = True


# --- Utility functions ----------------------------------------

# n is -1 or +1, depending on direction of input
def setISO (n):
	global iso
	iso = isoRange[ max(min(isoState + n, 0), len(isoRange)) ];

# n is -1 or +1, depending on direction of input
def setShutterSpeed (n):
	global shutter_speed


# returns number of captures needed [0], and shutter speed per capture [1]
def captures_needed (ss):
	total_snaps = int(math.ceil(ss / 1000000.0));
	per_shot_ss = ss / total_snaps
	return (total_snaps, per_shot_ss)

def capture ():
	global camera, shutter_speed

	filename = datetime.datetime.now().strftime("%Y-%m-%d--%H.%M.%S")

	if still_mode:
		shots = captures_needed(shutter_speed)
		print shots[0]

		if (shots[0] == 1):
			print "snap: " + str(shots[1] / 1000000.0) + " s"
			# set up camera with correct settings
			#camera.capture(filename + '.jpg')
		else:
			# create a blank image (best filled black, which is default)
			#composite = PIL.Image.new(size=(3000,2000))

			# set up camera with correct settings
			# camera.capture_sequence([
			# 	filename + '-%02d.jpg' % i
			# 	for i in range(shots[0])
			# ])
			
			# capture intermediate shots and add colour values to create composite
			for i in range(shots[0]):
				print "snap: " + str(shots[1] / 1000000.0) + " s"

				# add capture to composite image
				# open capture as image
				#capture = PIL.Image.open(filename + '-%02d.jpg' % i)
				#composite = PIL.ImageChops.add(composite, capture);

			# store composite
			# delete intermediate shots (for now, keep for testing)
		
		# show new-fangled capture in viewer
	else:
		# capture video
		# make sure iso + shutter_speed is set to auto (for now use exp_comp to adjust?)
		# also show on display
		pass


# --- Main control ---------------------------------------------

# Main loop
while(True):
	capture()
	break
