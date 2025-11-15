# Rotoforge README
![picture of first working iteration of Rotoforge to print a 10 mm tall wall with Al1100 wire]()


This is  **Rotoforge**, a 3D printer that uses continuous [friction welding](https://en.wikipedia.org/wiki/Friction_welding) to print metals, plastics and ceramics heterogeneously. 
If a wire is fed into the contact patch of a [wheel](https://en.wikipedia.org/wiki/Wheel_and_axle) which is spinning fast enough and with sufficient torque, the wire will heat up due to [friction](https://en.wikipedia.org/wiki/Friction), and become more flowable(see [thixotropy](https://en.wikipedia.org/wiki/Thixotropy)) due to plastic shear(see [flow stress](https://en.wikipedia.org/wiki/Flow_stress) and the [Zener-Hollomon Parameter](https://en.wikipedia.org/wiki/Zener%E2%80%93Hollomon_parameter)). 

Under these conditions, even materials like aluminum, copper, steel, glass, and high grade engineering plastics will become extremely fluid (without melting) and bond (given the correct contact and mixing conditions) at the contact patch, in air, without a [shield gas](https://en.wikipedia.org/wiki/Shielding_gas)!, at relatively low temperatures  and pressures. This allows relatively low force, FDM like printing of these materials on a standard 3D printer, given a way to feed wire, and a wheel with adequate speed and torque to keep the material flowing under the chosen RPM and feed rate conditions. 
This printing process, like [forging](https://en.wikipedia.org/wiki/Forging), can yield material which is stronger as printed, than the initial feedstock. 

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
Source files, including complete CAD data for the mechanical parts, and electronics and source code to build and operate your own Rotoforge on an Ender 3 motion platform.  Principally rotoforge can be built on any motion platform, and more rigidity is better, but not strictly neccessary.

## Mechanical Parts
Rotoforge is currently just a mechanical and electronics attachment for an FDM printer which enables continuous friction welding as the new mode of energy injection and material deposition. the original mechanical CAD files are native to **Fusion360**. 
I intend to provide OpenSCAD or similar fully open source versions in the future. 

## Electronic parts
Rotoforge electronics are modeled in KiCAD and EaglePCB.  There are off the shelf versions available as well that do the job. Mostly you will need:
In the US: a 110->240 volt step up transformer.
a Variac or other method to control the speed of the flex shaft grinder (not required but useful).
A >800 watt flex shaft grinder(sometimes called a "rotary tool" or "flexshaft die grinder").

## Software
There is presently only simple demo software for Rotoforge, as it runs on the motion control code and firmware of a typical FDM machine. All you will need to do to start exploring is install the mechanical and electronic parts, and use your slicer of choice (or use my provided python g-code generator) to adjust your feeds and speeds to suit the requirements of printing metals, plastics and potentially ceramics of your choice. **There is currently very little information in the wild on what feeds and speeds will work so this is a big point of ongoing exploration and where almost anyone could help!**  


Rotoforge software is licensed under the [AGPL-V3](https://www.gnu.org/licenses/agpl-3.0.en.html)

Rotoforge hardware is licensed under the [CERN Open Hardware License-strong](https://cern-ohl.web.cern.ch/)

There is a video assembly guide for this printer modification [here](https://www.youtube.com/watch?v=yMjR5zOKrdI&t=20s&ab_channel=Rotoforge)
There are ongoing blogs and technical details on development of the hardware, physics and materials science involved in this project [here](https://dailyrotoforge.blogspot.com/)
