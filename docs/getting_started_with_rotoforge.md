# How to build a rotoforge
1. download the repo
2. open the [bill of materials](https://github.com/Sindry-Manufacturing/rotoforge/blob/29fc23453d98a2a53141974132ee8f29831c75b1/docs/billsofmaterials/Rotoforge%20BOM%2011152025.ods) (BOM) in the billsofmaterials directory 
3. source the parts you can buy, build/have built the small number of custom parts (or print them)
4. assemble the parts
5. start printing and [experimenting](https://github.com/Sindry-Manufacturing/rotoforge/blob/29fc23453d98a2a53141974132ee8f29831c75b1/docs/getting_started_afrbplayground.md). Get started faster with my [afrb playground script](https://github.com/Sindry-Manufacturing/rotoforge/blob/29fc23453d98a2a53141974132ee8f29831c75b1/src/afrb_playground_gui(2).py)
6. Share what you learn with all of us on [Discord](https://discord.gg/T6tJYQXE26) 

Wondering how you can help? 


# Ways you could help the project

1. **4th-5th-6th axis** for certainty and better precision for curvy shapes

2. **better designs** for wire guide shoes, that can work(not stick to the wire, do a reasonable job of preventing clogging of the wire guide, prevent wire buckling as it is fed into the wheel, heat the wire up to ~600 C at least) 

3. **slicer mods** (custom slicer? or something) that respects the particular requirements of the wheel and leverages the unique properties of metal and the wheel process to make parts in ways that may not be exactly like FDM. and will probably have some advantages and disadvantages comparatively.  i got GPT to get a probably pretty bad start on it that produces results that look reasonable but maybe are not totally printable yet. There are few if any safety checks for printability, though the generally requirements of printing with the wheel appear to be respected. 

4. **closing the loop on the wheel itself.** 
I am currently running everything open loop like a caveman. Controlling velocity/torque/position control on the wheel could all be useful (in addition to temperature) to tell us more about what is actually happening at the deposition zone. (which would be a matter of broad research/general user/commercial interest beyond just printing single alloys)
I am currently planning to obtain a high speed camera(probably a chronos or similar) to really look closely at what is happening (get some glory shots) and try to connect the effects we can see with motor control conditions and operating points. Trying to do a better job of mapping the whole printing parameter space as much as I can... this is a huge lift and will take a long time on my own...but I think will be well worth the money and time to speed up slicing parameter development and familiarizing (myself) people with the concept and how it works....if anyone ends up implementing a spindle on head approach or otherwise using a BLDC that would benefit from such control it would be  of great service. 

I think if we want to go for smaller wheels, or higher wheel speeds (60-100K RPM) to get process forces even lower, further increase deposition rates, and allow for finer features, this is going to be an important step that I initially started on by then tried to simplify away with the big brushed DC motor die grinder currently on my prototype. I accepted the lower speed and 50 mm diameter  wheel to be able to prove function. 
the move to software controlled closed loop high speed BLDC drive is going to be a significant challenge and involves to many steps for me to tackle simultaneously. But if someone else wants to give it a try that would be awesome. 

5. **build implementations of the same basic concept**....others building roll bonders would be incredibly helpful, because then the onus is not always on me to be iterating the hardware and we can get more perspective on how to make it physically better and simplify the design to its most essential elements. I would consider this project a success when we can take the printer we have designed, throw it to a random joe in a remote (but electricity having) corner of the amazon rainforest, and have them be able to use it make something of use to them. Like a tool, or replacement part for a motor bike or car, or some structural part for their homes/businesses. 

6. **Help with planning, documenting, and thinking about what the future of the project looks like** where do people want to see this go? would anyone buy this if it looked like a product? maybe it should be more like a voron style thing?  I have my own ideas about what I want it to be, but I need more perspective to make informed decisions about how to organize things when we stat to get more serious with the system and push it beyond just working proof of concept.

7. **building local feedstock production**....wires of the diameters we need are not easy to find at affordable prices in small quantities for every alloy. 
right now we are basically limited to naval brass, 510 bronze, pure copper, al1100, mild carbon steel, 1080 spring steel, 304/316stainless steel, 5054 aluminum and a few others in the (24 AWG) ~0.5mm and smaller diameter we require. Basically what can be ordered small batch from china or elsewhere. 

A small bench top and low power electric and mostly automatic (reasonably reliable(90% uptime for 24/7 operation) wire drawing system that can take larger diameter wires (up to ~3mm rod perhaps) and draw it down to 0.5mm or smaller and spool that wire onto a roll (perhaps annealing in line to relax the stress of drawing) would be extremely helpful. (more than tripling our available feed stock options) 

I intend to do this myself eventually, and try for as much vertical integration as possible if that is what must be done to see this technology made manifest. 

8. **Documentation help** someone with the time, will, energy and know how to keep track of what is going on here in the discord and elsewhere, and document the goings on in a broader externally accessible, permanently linkable and indexable wiki or similar such thing. I am not a web admin or web designer, and while the task is easier than it ever has been with an LLM the job of managing that system is itself a bit too much for me to do continuously. I mostly operate by making all at once updates condensed from my aggregated notes, discord posts, and personal video logs/ writings each time I make a video, then I update the github and Mkdocs to reflect those changes (ideally in reverse order)....This is obviously a very poor way to do things and would benefit from a more skilled and consistent hand. 