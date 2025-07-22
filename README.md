# TV-B-Gone for raspberry pi
This repository contains implementation of the TV-B-Gone project, it is in simple terms universal remote that turns off all televisions within its range. Original TV-B-Gone was created by Mitch Altman, nowdays, there are a lot of implementations, but I have never seen any for raspberry pi, so this is it. I also added option to save and replay your own codes with irrp.py - IR example from official pigpio library. 
# Requirements
The script requires pigpio library to work, you can install it by running:
```
wget https://github.com/joan2937/pigpio/archive/master.zip
unzip master.zip
cd pigpio-master
make
sudo make install
```
# Usage
To use the script, make it executable with chmod and then simply run it with bash.
```
sudo chmod +x menu.sh
./menu.sh
```
It will enable pigpiod and throw you to menu, where you can choose either running TV-B-Gone codes, or save, replay, delete your custom code and also exiting the script, this will also kill pigpiod.
# Transmitter circuit
# Receiver circuit
# External references
- https://learn.adafruit.com/circuitpython-tv-zapper-with-circuit-playground-express/overview
- https://github.com/bikeNomad/micropython-tv-b-gone
- https://abyz.me.uk/rpi/pigpio/index.html
- https://www.tvbgone.com/
# TO DO
- Fix some errors - doubled text, cancel function
- More functions, possibilities...
