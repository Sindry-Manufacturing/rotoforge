# Rotoforge README

Rotoforge software is licensed under the [AGPL-V3](https://www.gnu.org/licenses/agpl-3.0.en.html)

Rotoforge hardware is licensed under the [CERN Open Hardware License-strong](https://cern-ohl.web.cern.ch/)

There is a video assembly guide for this printer modification [here](https://www.youtube.com/watch?v=yMjR5zOKrdI&t=20s&ab_channel=Rotoforge)
There are ongoing blogs and technical details on development of the hardware, physics and materials science involved in this project [here](https://dailyrotoforge.blogspot.com/)

This is  **Rotoforge**, a modification of an FDM printer that uses a combination of [friction extrusion](https://en.wikipedia.org/wiki/Friction_extrusion) / small scale [extrusion machining](https://docs.lib.purdue.edu/dissertations/AAI10830464/) to print metals, plastics and ceramics heterogeneously. In short, a standard 1.4-1.75 mm OD wire of feed material is pushed by a pinch wheel extruder with hardened steel gears into the hollow shaft of a brushless dc motor. At the end of this motor, a "tool" or "die" or "nozzle" is threaded onto the end of the shaft, blocking the wire from exiting. If a hole is drilled in this "nozzle", and the motor used to spin the nozzle at sufficient RPM, when the feed material is pushed into the spinning nozzle, it will heat up due to friction, and become more flowable(see [thixotropy](https://en.wikipedia.org/wiki/Thixotropy)) due to plastic shear(see [flow stress](https://en.wikipedia.org/wiki/Flow_stress)) by rotation with the nozzle. When this occurs, even materials like aluminum, steel, glass, and high grade engineering plastics will become extremely fluid and extrude (given the correct conditions) through the hole in the "nozzle". This principally enables FDM like printing of these materials on a standard 3D printer, given the correct nozzle geometry, and the appropriate RPM and feed rate conditions.

 If you would like to download the part files, schematics and documentation including text assembly tutorials and a getting started guide, clone the repository, or download the zipped folder here on github. 
We also have a [youtube channel](https://www.youtube.com/channel/UCBE1bfTLnz7WSu8h5rG6ihA) and a [read the docs page](https://www.rotoforge.com/introduction/).

If you want regular updates on progress from Michael, he has a [blog](https://dailyrotoforge.blogspot.com/) he updates periodically. 

For more active discussions we have a [discord channel](https://discord.gg/T6tJYQXE26) and a subreddit. 

for proper data storage on feeds and speeds and other printing and deposition parameters as well as in process data storage we have a [zenodo repository:](https://zenodo.org/records/10365783)

and we are occasionally active on the GOSH [community forums:](https://forum.openhardware.science/t/rotoforge-an-affordable-open-source-multimaterial-3d-printer-for-printing-metal-plastic-and-ceramics-on-the-home-desktop/4570/11)

# Files

Included in this Rotoforge repository are:
a bill of materials
guidelines for contributing
Documentation files to get the new user started and provide some basic guidance for troubleshooting
Source files, including complete CAD data for the mechanical parts, and electronics and source code to build your own Rotoforge on an Ender 3 motion platform.  Principally rotoforge can be built on any motion platform, and more rigidity is better, but not strictly neccessary.

## Mechanical Parts

Rotoforge is mostly a mechanical and electronics attachment for an FDM printer which enables friction extrusion as the new mode of energy injection and material deposition. the original mechanical CAD files are native to **Fusion360**. I intend to provide OpenSCAD or similar fully open source versions in the future. there is presently no software for Rotoforge, as it runs on the motion control code and firmware of a typical FDM machine. All you will need to do to start exploring is install the mechanical and electronic parts, and use your slicer of choice to adjust your feeds and speeds to suit the requirements of printing metals, plastics and potentially ceramics of your choice. **There is currently very little information in the wild on what feeds and speeds will work so this is a big point of ongoing exploration and where almost anyone could help!**  

## Electronic parts
Rotoforge electronics are modeled in KiCAD and EaglePCB.  There are off the shelf versions available as well that do the job. Mostly you will need:
A servo controller
A BLDC(brushless DC motor, 2270 KV or higher, with a hollow shaft... or perhaps with a belted connection to a hollow spindle)
A ESC for the BLDC (An engine speed controller, to facilitate control of the BLDC and its RPM)
A DC benchtop power supply, or power from the printer platform you are using(to power the BLDC and perhaps the other components)
A buck converter to provide the 11 volts the BLDC requires
A control board for the 3D printer / CNC frame you have selected. (The parts are made for the Ender 3 right now, but can be adapted to fit almost anything)
**A dedicated all in one, tunable power converter of ~200 watt capability, with an integrated ESC and PWM control interface for manual tuning and connection to existing PWM control signals available on 3D printer control boards would be of value here...**


## Software

Presently, we are searching the parameter space for rotoforge manually by adjusting slicer settings and motor speed to control how material gets fed, and how fast it is deposited on the build plate surface. RPM is not a direct replacement for hotend temperature as shear and frictional heat are also contact force related, which is dependent on the force exerted by the extruder. There is abundant opportunity for new control code development, closed loop control (as the motor and ESC hardware provides current, power and temperature feedback directly) and some machine learning and materials physics prediction opportunities. Unlike conventional FDM, the motor power is much more directly coupled to the state of the feed material as it flows through the tool, and so in principle provides much tighter monitoring of the material state at every step of the deposition process. An enterprising software developer may find this of interest. 

There is also a distinct and exciting possibility that, through characterizing the [shear viscosity to entropy density ratio](https://www.osti.gov/pages/servlets/purl/1249122) we could develop a universal, predictive model of material flow behavior at any temperature and at any shear rate, thereby facilitating fully automated prediction of necessary printing parameters on the fly without human intervention.  This would conceivably allow generalizable 3D printing of heterogeneous materials in a fully automated fashion, provided some additional computer control via vision software and print tack analysis via LIDAR or visual identification can be integrated. 

**TLDR; Rotoforge enables much better closed loop sensing and control of the material printing process and could enable fully automated heterogeneous material manufacturing with appropriate software developemnt.**
