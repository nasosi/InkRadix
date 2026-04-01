# InkRadix v 0.9.0: An Inkscape extension for editable Radical Pie Equations
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
import sys
import copy
import shlex
import winreg
import hashlib
import tempfile
import subprocess
import inkex

from lxml import etree


DEBUG = False


SVG_DEFAULT_CONTENT          = """<svg width="6pt" height="8pt" viewBox="0 -8 6 8" version="1.1" xmlns="http://www.w3.org/2000/svg"><desc>Radical Pie Equation</desc><!--D{} Gr { Bg {}}--></svg>"""
DEFAULT_RADICAL_PIE_EXE_PATH = r"C:\Program Files\RadicalPie\RadicalPie.exe"
INKRADIX_NAMESPACE           = "https://github.com/nasosi/InkRadix/ns"
IR                           = f"{{{INKRADIX_NAMESPACE}}}"
SVG_DRAWABLE_TAGS            = {"path", "g", "text", "line", "rect", "circle", "ellipse", "polygon", "polyline"}

etree.register_namespace( "inkradix", INKRADIX_NAMESPACE )


def DecodeNumericEntities( text ):

    def repl( match ):

        value = match.group( 1 )

        try:

            if value and value[0] in "xX":

                num = int( value[1:], 16 )

            else:

                num = int( value, 10 )

            if 0 <= num <= 0x10FFFF:

                return chr( num )

        except ( ValueError, OverflowError ):

            pass


        return match.group( 0 )

    return re.sub( r"&#(x?[0-9A-Fa-f]+);", repl, text )


def NormalizeExePath( path ):

    if not path:

        return None

    path = path.strip( )

    if not path:

        return None

    if path[ 0 ] in ( '"', "'" ):

        try:

            parts = shlex.split( path, posix=False )
            exe   = parts[ 0 ] if parts else None

        except ValueError:

            exe = path.strip( '"' ).strip( "'" )

        return exe


    if os.path.exists( path ):

        return path


    firstPart = path.split( " " )[ 0 ]

    return firstPart if firstPart else None



def FileHash( path ):

    h = hashlib.sha256( )

    with open( path, "rb" ) as f:

        for chunk in iter( lambda: f.read( 8192 ), b"" ):

            h.update( chunk )

    return h.hexdigest( )



def ReadRegistryValue( root, subkey, valueName ):

    try:

        with winreg.OpenKey( root, subkey, 0, winreg.KEY_READ ) as key:

            value, _ = winreg.QueryValueEx( key, valueName )

            return value

    except FileNotFoundError:

        return None

    except OSError as e:

        raise RuntimeError( f"Registry access error: {e}" )


class InkRadix( inkex.EffectExtension ):

    def DebugMsg( self, msg):

        if DEBUG:

            self.msg( msg )


    def FindRadicalPieExecutablePath( self ):

        root      = winreg.HKEY_CLASSES_ROOT
        subkey    = r"CLSID\{4EE860BB-53CE-44F3-BC6B-434146CAB233}\LocalServer32"
        valueName = ""
        exePath   = None

        regValue = ReadRegistryValue( root, subkey, valueName )
        if regValue:

            exePath = NormalizeExePath( regValue )

            if exePath and os.path.exists( exePath ):

                self.DebugMsg( f"RadicalPie executable found in registry: {exePath}" )
                return exePath

            elif exePath:

                self.DebugMsg( f"Registry path exists but file not found: {exePath}" )

            else:

                self.DebugMsg( f"Registry value could not be normalized: {regValue}" )

        if os.path.exists( DEFAULT_RADICAL_PIE_EXE_PATH ):

            self.DebugMsg( f"Using default RadicalPie path: {DEFAULT_RADICAL_PIE_EXE_PATH}" )
            return DEFAULT_RADICAL_PIE_EXE_PATH


        self.DebugMsg( "RadicalPie executable not found." )

        return None


    def IsInkRadixElement( self, node, name ):

        if not isinstance( node.tag, str ):

            return False

        qname = etree.QName( node )

        return qname.localname == name and qname.namespace == INKRADIX_NAMESPACE


    def IsRadicalPieObject( self, elem ):

        for node in elem.iter( ):

            if self.IsInkRadixElement( node, "datav1" ):

                if node.text and node.text.strip( ):

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


    def ConvertRadicalPieXMLToComments( self, group ):

        for node in list( group.iter( ) ):

            if self.IsInkRadixElement( node, "radicalpie" ):

                data_elem = None
                for child in node:

                    if self.IsInkRadixElement(child, "datav1"):

                        data_elem = child
                        break

                text = data_elem.text if data_elem is not None else ""

                comment = etree.Comment( text or "" )

                parent = node.getparent( )
                if parent is not None:

                    parent.replace( node, comment )

                else:

                    self.DebugMsg( "ConvertRadicalPieXMLToComments: Node had no parent during replacement" )


    def ConvertCommentsToRadicalPieXML( self, group ):

        for node in list( group.iter( ) ):

            if isinstance( node, etree._Comment ):

                text = DecodeNumericEntities( node.text or "" ).strip( )

                if not text:

                    continue

                rp_elem = etree.Element( IR + "radicalpie" )
                data_elem = etree.SubElement( rp_elem, IR + "datav1" )
                data_elem.text = text

                parent = node.getparent( )
                if parent is not None:

                    parent.replace( node, rp_elem )

                else:

                    self.DebugMsg( "ConvertCommentsToRadicalPieXML: Node had no parent during replacement" )


    def WriteInputSvg( self, svgFilePath, editingGroup ):

        if editingGroup is not None:

            newSvg = etree.Element( '{http://www.w3.org/2000/svg}svg' )
            newSvg.set( "version", "1.1" )

            groupCopy = copy.deepcopy( editingGroup )

            self.ConvertRadicalPieXMLToComments( groupCopy )

            newSvg.append( groupCopy )

            etree.ElementTree( newSvg ).write( svgFilePath, encoding="utf-8", xml_declaration=True )

        else:

            with open( svgFilePath, "w", encoding="utf-8" ) as f:

                f.write( SVG_DEFAULT_CONTENT )


    def RunRadicalPie( self, svgFilePath ):

        radicalPieExePath = self.FindRadicalPieExecutablePath( )

        if radicalPieExePath is None or not os.path.exists( radicalPieExePath ):

            raise inkex.AbortExtension(
                "Radical Pie Executable not found. "
                "This extension requires an installation of the Radical Pie Equation Editor "
                "(https://radicalpie.com/)."
            )

        try:

            beforeHash = FileHash( svgFilePath )

        except Exception as e:

            beforeHash = None
            self.DebugMsg( f"Before hash failed for {svgFilePath}: {e}" )

        try:

            subprocess.run( [ radicalPieExePath, svgFilePath ], check=True,  )

        except FileNotFoundError:

            raise inkex.AbortExtension( f"RadicalPie executable not found at: {radicalPieExePath}" )


        if not os.path.exists( svgFilePath ):

            raise inkex.AbortExtension( "Logical error: Output SVG vanished!" )

        try:

            afterHash = FileHash( svgFilePath )

        except Exception as e:

            afterHash = None
            self.DebugMsg( f"After hash failed for {svgFilePath}: {e}" )

        if beforeHash is None or afterHash is None:

            self.DebugMsg(" Hash comparison unavailable. Assuming file changed." )
            return True

        return beforeHash != afterHash



    def ParseOutputSvg( self, svgFilePath ):

        parser = etree.XMLParser( recover=True, remove_comments=False, huge_tree=True )
        tree = etree.parse( svgFilePath, parser )
        root = tree.getroot( )

        hasContent = any(
            isinstance( node.tag, str ) and
            node.tag.startswith( "{" ) and
            node.tag.split( "}", 1 )[ 1 ] in SVG_DRAWABLE_TAGS
            for node in root.iter()
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

        self.ConvertCommentsToRadicalPieXML( newGroup )

        return newGroup


    def ApplyResultGroup( self, newGroup, editingGroup ):

        if editingGroup is not None:

            if 'transform' in newGroup.attrib:

                self.DebugMsg("Warning: RadicalPie returned a transform, overriding it.")


            originalTransform = editingGroup.attrib.get('transform')
            if originalTransform:

                newGroup.set('transform', originalTransform)

            parent = editingGroup.getparent( )
            if parent is None:

                raise inkex.AbortExtension("Editing group has no parent.")

            parent.replace( editingGroup, newGroup )

            self.DebugMsg( "Selection replaced with updated RadicalPie SVG." )

        else:

            layer = self.svg.get_current_layer( )
            layer.append( newGroup )

            self.DebugMsg( "New RadicalPie SVG added." )


    def PrepareTempFile( self, editingGroup ):

        tmpFile = tempfile.NamedTemporaryFile( suffix=".svg", delete=False )
        svgFilePath = tmpFile.name
        tmpFile.close( )

        self.WriteInputSvg( svgFilePath, editingGroup )

        return svgFilePath


    def ApplyChanges( self, changed, editingGroup, svgFilePath ):

        if not changed:

            self.DebugMsg( "RadicalPie did not modify the file. Original preserved." )
            return

        root = self.ParseOutputSvg( svgFilePath )

        if root is None:

            self.DebugMsg( "Output SVG is empty. Original preserved." )
            return

        newGroup = self.BuildGroupFromRoot( root )

        self.ApplyResultGroup( newGroup, editingGroup )


    def effect( self ):

        if sys.platform != "win32":

            raise inkex.AbortExtension(
                "InkRadix extension only works on Windows RadicalPie integration requires a Windows system."
            )


        svgFilePath = None

        try:

            editingGroup = self.FindEditingGroup( )
            svgFilePath  = self.PrepareTempFile( editingGroup )
            changed      = self.RunRadicalPie( svgFilePath )

            self.ApplyChanges( changed, editingGroup, svgFilePath )

        except subprocess.CalledProcessError as e:

            raise inkex.AbortExtension( f"External program failed: {e}" )

        except etree.XMLSyntaxError as e:

            raise inkex.AbortExtension( f"Invalid SVG output: {e}" )

        except Exception as e:

            raise inkex.AbortExtension( f"Unexpected error: {e}" )

        finally:

            if svgFilePath and os.path.exists( svgFilePath ):

                try:

                    if DEBUG:

                        self.msg( f"Temp file preserved at: {svgFilePath}" )

                    else:

                        os.remove(svgFilePath)

                except Exception:

                    pass


if __name__ == '__main__':

    InkRadix( ).run( )
