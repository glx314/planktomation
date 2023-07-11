# Planktomation 

This is a small Python module to interact with a [Plankstoscope](https://www.planktoscope.org/). This allows to write simple automation scripts.

This module uses RPi.GPIO which can only be run on a Raspberry Pi. This module is used to interact directly with the lights of the device. So, the script has to be located and run from the Rasberry Pi of your Planktoscope.

# Installation

Get the code from this repository, cd into it, and then :

    pip install .

## Example code

    from planktomation import Planktoscope

    NLOOP = 10

    logger.info("Starting planktoscope automation script")

    planktoscope = Planktoscope()
    for j in range(NLOOP):
        logger.info(f"Starting acquisition loop {j}/{NLOOP}")

        # Switch on the light and setup the camera
        planktoscope.switch_light(True)
        planktoscope.iso(100)
        planktoscope.shutter_speed(500)
        planktoscope.auto_white_balance()
        
        # Fill the water pipe
        planktoscope.pump(True, 10, 10) 
        
        #Get some images
        planktoscope.acquire_frames(5)
        
        # Switch off the light
        planktoscope.switch_light(False)
        
        # Empty the water pipes
        planktoscope.pump(False, 10, 10, wait=False)