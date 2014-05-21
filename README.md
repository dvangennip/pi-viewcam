# Pi Viewcam
-------------------
This code enables a Raspberry Pi camera module to function as the digital back for a view camera. It assumes some structure is available to place and hold the hardware in position, and that a display is available. The use as a digital back implies the necessity of manual control, given by this application. Settings can be adjusted on screen or via a rotary encoder.

#### Inspiration
-------------------
* [Adafruit Raspberry Pi WiFi Touchscreen camera](https://learn.adafruit.com/diy-wifi-raspberry-pi-touch-cam)
* [Adafruit-pi-cam code](https://github.com/adafruit/adafruit-pi-cam)

## Core features
-------------------
* Manual control over Raspberry Pi camera module.
* Visual feedback and control via PiTFT display.

## Hardware
-------------------
* Raspberry Pi B
* Raspberry Pi camera module
* Adafruit PiTFT 2.8" display with touchscreen input
* Rotary encoder (to adjust settings + center button for taking photos)

## TODO
-------------------
* make sure preview stops after some time
* make settings adjustable
* make some way to switch between preview mode and review mode
* include a timer mode (set delay)
* incorporate rotary encoder (adjust LED colour to type of setting? flash during delayed capture)
* use PiTFT display for all visual feedback
* load settings from last time
* have a proper shutdown routine
* implement video mode
* turn off display during capture / set to black (for dark environment shots)
* include a way to trigger a connected flash (if capture can be timed accurately)

## Depencies
-------------------
* [python-picamera](http://picamera.readthedocs.org/en/latest/)
* [Pillow](http://pillow.readthedocs.org/en/latest/)
* pygame

## License
-------------------
You are free to use this code as you see fit, with no obligations attached. It would be nice to see interesting use cases.
