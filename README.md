# InkRadix
<div align="center">
<p align="center">
  <img src="Resources/InkRadixDemo.png"/>
</p>
</div>
InkRadix is an Inkscape extension that enables editable equations with Radical Pie™ (https://radicalpie.com/). Radical Pie currently runs on Windows.

# Installation
There are several ways to install InkRadix:

## Option 1: Easiest
If you have Windows version 10 1803 or later (very likely), you can install easily with:
1. Open a Command Prompt
2. Execute the following command:
```
(if exist "%temp%\InkRadixInst" rmdir /s /q "%temp%\InkRadixInst") && md "%temp%\InkRadixInst" && curl -L -o "%temp%\InkRadixInst\main.zip" "https://github.com/nasosi/InkRadix/archive/refs/heads/main.zip" && powershell -Command "Expand-Archive -Path '%temp%\InkRadixInst\main.zip' -DestinationPath '%temp%\InkRadixInst' -Force" && cd /d "%temp%\InkRadixInst\InkRadix-main\Resources" && call Install.bat && cd /d "%temp%" && rmdir /s /q "%temp%\InkRadixInst"
```
3. (Re)start Inkscape to load the extension.
   
## Option 2: Installer script
1. Download this repository [here](https://github.com/nasosi/InkRadix/archive/refs/heads/main.zip).
2. Extract it.
3. Execute the ```Install.bat``` script from the ```Resources``` folder.
4. (Re)start Inkscape to load the extension.

## Option 3: Manual
1. Download this repository [here](https://github.com/nasosi/InkRadix/archive/refs/heads/main.zip).
2. Place the files ```InkRadix.inx``` and ```InkRadix.py``` in the following user directory: ```%APPDATA%\inkscape\extensions``` You can copy and paste this path directly into the Windows File Explorer address bar. It will resolve to a folder similar to: ```C:\Users\<YourUsername>\AppData\Roaming\inkscape\extensions```
3. (Re)start Inkscape to load the extension.

## Option 4: From within Inkscape
1. Download this repository [here](https://github.com/nasosi/InkRadix/archive/refs/heads/main.zip).
2. In Inkscape, select ```Extensions``` → ```Manage Extensions```
3. In the Extensions window that appears, select the ```Install Packages``` tab.
4. At the bottom of the window, select the folder icon.
5. Navigate to the location where  ```InkRadix-main.zip``` was download it, select it and click ```Open``` at the bottom right of the window.
6. Close the Extensions window and restart inkscape.

# Usage
The extension adds a menu entry under Extensions → Text → Radical Pie Equation.

- **Adding a new equation**: If no objects are selected, the extension will launch Radical Pie. After closing and saving, a new equation will be inserted into Inkscape.
- **Editing an existing equation**: If an existing Radical Pie equation is selected, running the command will open it for editing. After closing and saving, the selected object will be updated with the modified content.
- You can **paste LaTeX** equations into Radical Pie, and they will be formatted automatically. You can then modify them graphically if needed.
- If you want a **LaTeX-like appearance**, you can install the NewCM-Radix font collection (https://github.com/nasosi/NewCM-Radix
), which works seamlessly with Radical Pie.
- Avoid ungrouping the equation object in Inkscape, as this will make it no longer editable. If this happens by accident, you can restore it using the Undo function.
