%
(toolpathsforrotoforgeinserttoolholder)
(Machine)
(  vendor: Autodesk)
(  model: Generic 3-axis)
(  description: This machine has Y axis on the Table and XZ axis on the Head)
(T2  D=0.7 CR=0 TAPER=118deg - ZMIN=-3.175 - drill)
G90
G17
G21
G28 G91 Z0
G90

(Drill1)
T2 M6
S10000 M3
G54
M7
G0 X0 Y-0.6
Z18.175
Z8.175
G1 Z-3.175 F20
G0 Z8.175
Z18.175
M9
G28 G91 Z0
G90
G28 G91 X0 Y0
G90
M30
%
