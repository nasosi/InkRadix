# InkRadix
InkRadix is an Inkscape extension that enables editable equations with [Radical Pie™](https://radicalpie.com/).

# Installation
To install, place the files ```InkRadix.inx``` and ```InkRadix.py``` inside the following user directory:

```%appdata%\inkscape\extensions```

and (re)start Inkscape.

# Usage
The extension adds a menu entry under Extensions → Text → Radical Pie Equation.

- If the user has not selected any objects, the extension will launch Radical Pie, and upon closing and saving, it will insert a new equation into Inkscape.
- If the user has selected an existing Radical Pie Equation, executing the command will open Radical Pie for editing the equation, and upon closing and saving, the selection will be updated with the modified content.
- Avoid ungrouping the equation object, as this will make it no longer editable. If this happens accidentally, you can restore it using Undo

<div align="center">
<p align="center">
  <img src="Resources/InkRadixDemo.png"/>
</p>
</div>


