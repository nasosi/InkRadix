# InkRadix
<div align="center">
<p align="center">
  <img src="Resources/InkRadixDemo.png"/>
</p>
</div>
InkRadix is an Inkscape extension that enables editable equations with [Radical Pie™](https://radicalpie.com/).

# Installation
Currently, there are two suggested options:

## Option 1
Execute the ```Install.bat``` script from the ```Resources``` folder.

## Option 2
Place the files ```InkRadix.inx``` and ```InkRadix.py``` in the following user directory:

```%APPDATA%\inkscape\extensions```

You can copy and paste this path directly into the Windows File Explorer address bar. It will resolve to a folder similar to:

C:\Users\<YourUsername>\AppData\Roaming\inkscape\extensions

After copying the files, restart Inkscape to load the extension.

# Usage
The extension adds a menu entry under Extensions → Text → Radical Pie Equation.

- If no objects are selected, the extension will launch Radical Pie. After closing and saving, a new equation will be inserted into Inkscape.
- If an existing Radical Pie equation is selected, running the command will open it for editing. After closing and saving, the selected object will be updated with the modified content.
- Avoid ungrouping the equation object in Inkscape, as this will make it no longer editable. If this happens accidentally, you can restore it using the Undo function.
- You can paste LaTeX equations into Radical Pie, and they will be formatted automatically. You can then modify them graphically if needed.
- If you want a LaTeX-like appearance, you can install the NewCM-Radix font collection (https://github.com/nasosi/NewCM-Radix
), which works seamlessly with Radical Pie.




