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

- If the user has not selected any objects, the extension will launch Radical Pie, and upon closing and saving, it will insert a new equation into Inkscape.
- If the user has selected an existing Radical Pie Equation, executing the command will open Radical Pie for editing the equation, and upon closing and saving, the selection will be updated with the modified content.
- Avoid ungrouping the equation object, as this will make it no longer editable. If this happens accidentally, you can restore it using Undo.




