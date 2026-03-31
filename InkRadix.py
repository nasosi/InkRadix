# InkRadix v 0.5.0: An Inkscape extension for editable Radical Pie Equations
# 
# MIT License
#
# Copyright (c) 2026 Athanasios Iliopoulos
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import os
import re
import copy
import inkex
import winreg
import tempfile
import subprocess

from lxml import etree


DEBUG = False  


svgDefaultContent = """<svg width="6pt" height="8pt" viewBox="0 -8 6 8" version="1.1" xmlns="http://www.w3.org/2000/svg"><desc>Radical Pie Equation</desc><!--D{} Gr { Bg {}}--></svg>"""
defaultRadicalPieExePath = r"C:\Program Files\RadicalPie\RadicalPie.exe"


def DecodeNumericEntities( text ):

    def repl( match ):
    
        value = match.group( 1 )
        
        try:
            if value[0] in "xX":
            
                num = int( value[1:], 16 )
                
            else:
            
                num = int( value, 10 )


            if 0 <= num <= 0x10FFFF:
            
                return chr( num )

        except ( ValueError, OverflowError ):
        
            pass

        return match.group( 0 )

    return re.sub( r"&#(x?[0-9A-Fa-f]+);", repl, text )


def ReadRegistryValue( root, subkey, valueName ):
 
    try:
    
        with winreg.OpenKey( root, subkey, 0, winreg.KEY_READ ) as key:
        
            value, valueType = winreg.QueryValueEx( key, valueName )
            
            return value
            
    except FileNotFoundError:
        
        return None
    
    except OSError as e:
        
        raise RuntimeError( f"Registry access error: {e}" )
        
    
class InkRadix( inkex.Effect ):

    def DebugMsg( self, msg):
    
        if DEBUG:
        
            self.msg( msg )
            
            
    def FindRadicalPieExecutablePath( self ):
    
        root                        = winreg.HKEY_CLASSES_ROOT
        subkey                      = r"CLSID\{4EE860BB-53CE-44F3-BC6B-434146CAB233}\LocalServer32"
        valueName                   = ""
        registeredRadicalPieExePath = ReadRegistryValue( root, subkey, valueName );
              
        if registeredRadicalPieExePath:
        
            return registeredRadicalPieExePath;
            
            
        if os.path.exists( defaultRadicalPieExePath ):

            return defaultRadicalPieExePath;
            
        return None;
            
            
    def IsRadicalPieObject( self, elem ):

        for node in elem.iter( ):

            if node.tag.endswith( 'desc' ):

                if node.text and node.text.strip( ).startswith( "Radical Pie Equation" ):

                    return True

        return False


    def FindEditingGroup( self ):

        selected = self.svg.selection

        if not selected:

            return None

        for elem in selected.values( ):

            if elem.tag == inkex.addNS( 'g', 'svg' ) and self.IsRadicalPieObject( elem ):

                self.DebugMsg( "Editing existing RadicalPie group" )

                return elem

        return None


    def WriteInputSvg( self, svgFilePath, editingGroup ):

        if editingGroup is not None:

            newSvg = etree.Element( '{http://www.w3.org/2000/svg}svg' )
            newSvg.set( "version", "1.1" )

            groupCopy = copy.deepcopy( editingGroup )

            for node in groupCopy.iter( ):

                if isinstance( node, etree._Comment ):

                    node.text = DecodeNumericEntities( node.text )

            newSvg.append( groupCopy )

            etree.ElementTree( newSvg ).write( svgFilePath, encoding="utf-8", xml_declaration=True )

        else:

            with open( svgFilePath, "w", encoding="utf-8" ) as f:

                f.write( svgDefaultContent )


    def RunRadicalPie( self, exePath, svgFilePath ):

        beforeMtime = os.path.getmtime( svgFilePath )
        beforeSize = os.path.getsize( svgFilePath )

        subprocess.run( [ exePath, svgFilePath ], check=True )

        if not os.path.exists( svgFilePath ):

            raise inkex.AbortExtension( "Output SVG not found!" )

        afterMtime = os.path.getmtime( svgFilePath )
        afterSize = os.path.getsize( svgFilePath )

        return not ( afterMtime == beforeMtime and afterSize == beforeSize )


    def ParseOutputSvg( self, svgFilePath ):

        parser = etree.XMLParser( recover=True, remove_comments=False, huge_tree=True )
        tree = etree.parse( svgFilePath, parser )
        root = tree.getroot( )

        hasContent = any(
            node.tag.endswith( ( 'path', 'g', 'text', 'line', 'rect', 'circle' ) )
            for node in root.iter( )
        )

        if not hasContent:

            return None

        return root


    def BuildGroupFromRoot( self, root ):

        newGroup = etree.Element( inkex.addNS( 'g', 'svg' ) )

        newGroup.set( "id", self.svg.get_unique_id( "radicalpie-group" ) )
        newGroup.set( inkex.addNS( 'label', 'inkscape' ), "RadicalPie Output" )
        newGroup.set( inkex.addNS( 'groupmode', 'inkscape' ), 'group' )

        for node in root:

            newGroup.append( copy.deepcopy( node ) )

        return newGroup


    def ApplyResultGroup( self, newGroup, editingGroup ):

        if editingGroup is not None:

            parent = editingGroup.getparent( )

            if 'transform' not in newGroup.attrib and 'transform' in editingGroup.attrib:

                newGroup.set( "transform", editingGroup.attrib[ 'transform' ] )

            parent.replace( editingGroup, newGroup )

            self.DebugMsg( "Selection replaced with updated RadicalPie SVG." )

        else:

            layer = self.svg.get_current_layer( )
            layer.append( newGroup )

            self.DebugMsg( "New RadicalPie SVG added." )


    def effect( self ):

        radicalPieExePath = self.FindRadicalPieExecutablePath( )

        if radicalPieExePath == None:

            raise inkex.AbortExtension( "Radical Pie Executable not found. This Extensions needs an installation of the Radical Pie Equation Editor (https://radicalpie.com/)." )

        svgFilePath = None

        try:

            editingGroup = self.FindEditingGroup( )

            tmpFile = tempfile.NamedTemporaryFile( suffix=".svg", delete=False )
            svgFilePath = tmpFile.name
            tmpFile.close( )

            self.WriteInputSvg( svgFilePath, editingGroup )

            changed = self.RunRadicalPie( radicalPieExePath, svgFilePath )

            if not changed:

                self.DebugMsg( "RadicalPie did not modify the file. Original preserved." )

                return

            root = self.ParseOutputSvg( svgFilePath )

            if root is None:

                self.DebugMsg( "Output SVG is empty. Original preserved." )

                return

            newGroup = self.BuildGroupFromRoot( root )

            self.ApplyResultGroup( newGroup, editingGroup )

        except subprocess.CalledProcessError as e:

            raise inkex.AbortExtension( f"External program failed: {e}" )

        except etree.XMLSyntaxError as e:

            raise inkex.AbortExtension( f"Invalid SVG output: {e}" )

        except Exception as e:

            raise inkex.AbortExtension( f"Unexpected error: {e}" )

        finally:

            if svgFilePath and os.path.exists( svgFilePath ):

                try:

                    os.remove( svgFilePath )

                except Exception:

                    pass


if __name__ == '__main__':

    InkRadix( ).run( )