# Pi Viewcam
-------------------
This python code enables a Raspberry Pi with camera module to be controlled as a manual camera, giving full control over the exposure. This project should help me to use the RPi as a digital back for a view camera. Settings can be adjusted on screen or via a rotary encoder. It assumes some structure is available to place and hold the hardware in position, and that a display is available.

## Core features
-------------------
* Manual control over Raspberry Pi camera module.
* Visual feedback and control via PiTFT display.

## Using the software
-------------------
Instead of a small display, any monitor connected via HDMI will let you use the software. However, you'll need to use a keyboard if no other hardware input is available.

### Running the code
Using the pi-viewcam code requires root access to get access to the display and GPIO (the hardware pins). Navigate to the pi-viewcam folder on the RPi and start it as follows:

````sh
$ sudo python main.py
````

### GUI
*screenshot*

__Preview mode__ – Most of the screen is taken up by a live preview from the camera, the size of which depends on the capture mode and aspect ratio (4:3 or 16:9). The bottom row shows values for various settings (ISO, shutter speed, exposure compensation, capture mode). Tapping a setting's section allows to adjust the setting, with the active setting marked by a pink background. A white line above each section indicates the position of the current value within its range. When in any video capturing mode, the white line for shutter speed indicates the shutter angle (halfway means 180º, all the way to the right 360º).

*screenshot*

__Adjustment mode__ – Once a setting is activated, adjustments can be made via the hardware control, left or right on a connected keyboard, or by tapping on the pink strip near the desired value. Again, the white line serves as an indicator of the setting's value within the possible range.

*screenshot*

__Review mode__ – Some basic information about the photo or video is shown. Tap the display in the middle to zoom in or play the video. Tapping to the left or right side moves to the previous or the next image.

### Controls
*Rotary encoder / Keyboard equivalent*

````
Left	Adjust current setting
Right	Adjust current setting
Down	Confirm current setting / Capture (if no setting is active)
````

*On-screen buttons / Keyboard equivalent*

````
1		Make ISO current setting
2		Make shutterspeed current setting
3		Make exposure compensation current setting
4		Browse menu with additional settings
0		Make capturing mode current setting (keyboard only)
````

*Hardware buttons / Keyboard equivalent*

````
Esc		Quit immediately
Q		Quit / Return to preview mode
W		-
E		Switch preview effect / Zoom in or play video (in review mode)
R		Toggle review mode
````

## Inspiration
-------------------
* [Adafruit Raspberry Pi WiFi Touchscreen camera](https://learn.adafruit.com/diy-wifi-raspberry-pi-touch-cam) / [Adafruit-pi-cam code](https://github.com/adafruit/adafruit-pi-cam)
* Various projects that use a smaller sensor device to capture larger size specific lenses (especially common in digital video), via projection onto a ground glass focusing screen.

## Hardware required
-------------------
* Raspberry Pi (all models should work)
* Raspberry Pi camera module
* Adafruit PiTFT 2.8" display with touchscreen input
* Rotary encoder (to adjust settings + center button)

## Software dependencies
-------------------
* Tested only on Raspbian Wheezy, with a Raspberry Pi model B.
* [python-picamera](http://picamera.readthedocs.org/en/latest/)
* [Pillow](http://pillow.readthedocs.org/en/latest/) (also needs python-dev, python-setuptools, libjpeg-dev; install via pip)
* [PyGame](http://www.pygame.org/) (comes with Raspbian Wheezy)

Before installing, make sure the Raspberry Pi is up-to-date:

````sh
$ sudo rpi-update
$ sudo apt-get update && upgrade
````

The following commands should get everything you need:

````sh
$ sudo apt-get install python-dev python-setuptools python-picamera libjpeg-dev pygame pip gpac
$ sudo pip install pillow
````

## Known issues
-------------------
* Camera preview does not accurately reflect settings (gains, exposure, and WB can fluctuate).
* Adjusting the shutter speed any value above 1/15 s means the framerate has to be adjusted as well, which requires the camera module to restart. This causes a brief but noticable delay. Switching between capturing modes suffers from the same effect.
* The RPi camera module does not allow for exposures longer than 6 seconds. If longer exposures are used, the software will capture several images and blend those together.
* Some operations are fairly slow (such as reviewing images).
* Settings are not stored between sessions.
* Software has yet to be tested with an actual PiTFT display.

## License
-------------------
You are free to use this code as you see fit, with no obligations attached. It would be nice to see interesting use cases.
