# InkRadix v 0.9.2: An Inkscape extension for editable Radical Pie Equations
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
import winreg
import hashlib
import tempfile
import subprocess
import inkex

from lxml import etree


DEBUG = False


SVG_DEFAULT_CONTENT   = """<svg width="6pt" height="9pt" viewBox="0 -9 6 9" version="1.1" xmlns="http://www.w3.org/2000/svg"><desc>Radical Pie Equation</desc><!--D{} Gr { Bg {}}--></svg>"""
SVG_DRAWABLE_TAGS     = { "path", "g", "text", "line", "rect", "circle", "ellipse", "polygon",
                          "polyline" }
FALLBACK_RP_EXE_PATH1 = r"C:\Program Files\RadicalPie\RadicalPie.exe"
FALLBACK_RP_EXE_PATH2 = r"D:\Program Files\RadicalPie\RadicalPie.exe"

INKRADIX_NAMESPACE    = "https://github.com/nasosi/InkRadix/ns"
INKSCAPE_NAMESPACE    = "http://www.inkscape.org/namespaces/inkscape"
IR                    = f"{{{INKRADIX_NAMESPACE}}}"
IS                    = f"{{{INKSCAPE_NAMESPACE}}}"

etree.register_namespace( "inkradix", INKRADIX_NAMESPACE )

USE_AT_OPERATOR = hasattr(inkex.Transform, "__matmul__")

def DecodeNumericEntities( text ):

    """
    Decode numeric character references in a string to actual characters.
    
    Supports both decimal (e.g., &#65;) and hexadecimal (e.g., &#x41;) entities.
    
    Parameters:
        text (str): Input string containing numeric entities.
        
    Returns:
        str: String with numeric entities replaced by corresponding characters.
    
    Notes:
        Invalid or out-of-range numeric entities are left unchanged.
    """

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


def FileHash( path ):

    """
    Compute the SHA256 hash of a file.
    
    Parameters:
        path (str): File path to compute the hash for.
        
    Returns:
        str: Hexadecimal string of the SHA256 hash.
        
    Raises:
        IOError/OSError if the file cannot be read.
    """

    h = hashlib.sha256( )

    with open( path, "rb" ) as f:

        for chunk in iter( lambda: f.read( 8192 ), b"" ):

            h.update( chunk )

    return h.hexdigest( )



def ReadRegistryValue( root, subkey, valueName ):

    """
    Read a value from the Windows Registry.
    
    Parameters:
        root (winreg.HKEY_*): Root key, e.g., winreg.HKEY_CLASSES_ROOT
        subkey (str): Registry subkey path
        valueName (str): Name of the value to retrieve (empty string for default)
        
    Returns:
        str | None: Value if found, otherwise None
        
    Raises:
        RuntimeError: For access errors other than FileNotFoundError
    """

    try:

        with winreg.OpenKey( root, subkey, 0, winreg.KEY_READ ) as key:

            value, _ = winreg.QueryValueEx( key, valueName )

            return value

    except FileNotFoundError:

        return None

    except OSError as e:

        raise RuntimeError( f"Registry access error: {e}" )

def GetLocalBoundingBox( group ):
    
    """
    Get the bounding box of a group ignoring its transform.
    
    Parameters:
        group (inkex.Group): Group element whose bounding box is to be calculated.
        
    Returns:
        inkex.BoundingBox: Bounding box in local coordinates.
    
    Notes:
        Temporarily removes 'transform' to calculate local bounding box.
    """

    originalTransform = group.attrib.get('transform')
    
    if originalTransform:
        del group.attrib['transform']
    
    bBox = group.bounding_box( )           
    
    if originalTransform:
        group.set( 'transform', originalTransform )
        
    return bBox;

def GetAnchors( bBox ):

    """
    Return a dictionary of key anchor points for a bounding box.
    
    Parameters:
        bBox (inkex.BoundingBox): The bounding box of an object.
        
    Returns:
        dict: Mapping of anchor names to `inkex.Vector2d` points.
              Keys include: top-left, top-center, top-right, middle-left, center,
                            middle-right, bottom-left, bottom-center, bottom-right
    """

    return {
        "top-left":      inkex.Vector2d( bBox.left,     bBox.top ),
        "top-center":    inkex.Vector2d( bBox.center_x, bBox.top ),
        "top-right":     inkex.Vector2d( bBox.right,    bBox.top ),
        "middle-left":   inkex.Vector2d( bBox.left,     bBox.center_y ),
        "center":        inkex.Vector2d( bBox.center_x, bBox.center_y ),
        "middle-right":  inkex.Vector2d( bBox.right,    bBox.center_y ),
        "bottom-left":   inkex.Vector2d( bBox.left,     bBox.bottom ),
        "bottom-center": inkex.Vector2d( bBox.center_x, bBox.bottom ),
        "bottom-right":  inkex.Vector2d( bBox.right,    bBox.bottom )
    }


def GetNearestAnchor( point, bBox ): 
    
    """
    Find the nearest anchor point of a bounding box to a given point.
    
    Parameters:
        point (inkex.Vector2d): The reference point.
        bBox (inkex.BoundingBox): The bounding box to compare against.
        
    Returns:
        tuple[str, inkex.Vector2d]: (anchor_name, anchor_point)
    """

    nearestName, nearestPoint = min(
        GetAnchors( bBox ).items(),
        key=lambda kv: (kv[1] - point).length
    )
    return nearestName, nearestPoint


class InkRadix( inkex.EffectExtension ):

    def DebugMsg( self, msg):

        if DEBUG:

            self.msg( msg )


    def FindRadicalPieExecutablePath( self ):

        """
        Locate the RadicalPie executable.
    
        Checks the Windows Registry first, then two fallback paths.
    
        Returns:
            str | None: Path to RadicalPie executable if found, else None.
        """

        root      = winreg.HKEY_CLASSES_ROOT
        subkey    = r"CLSID\{4EE860BB-53CE-44F3-BC6B-434146CAB233}\LocalServer32"
        valueName = ""
        exePath   = None

        try:

            exePath = ReadRegistryValue( root, subkey, valueName )

        except Exception as e:

            self.DebugMsg(  "Warning: could not read Radical Pie executable path from registry."
                            "Trying fallbacks." )


        if exePath and os.path.exists( exePath ):

            self.DebugMsg( f"RadicalPie executable found in registry: {exePath}" )
            return exePath

        if os.path.exists( FALLBACK_RP_EXE_PATH1 ):

            self.DebugMsg( f"Using fallback RadicalPie path: {FALLBACK_RP_EXE_PATH1}" )
            return FALLBACK_RP_EXE_PATH1

        if os.path.exists( FALLBACK_RP_EXE_PATH2 ):

            self.DebugMsg( f"Using fallback RadicalPie path: {FALLBACK_RP_EXE_PATH2}" )
            return FALLBACK_RP_EXE_PATH2

        return None


    def IsInkRadixElement( self, node, name ):

        """
        Check if an XML node is an InkRadix element with a specific local name.
    
        Parameters:
            node (lxml.etree.Element): Node to check
            name (str): Expected local name
    
        Returns:
            bool: True if node matches InkRadix namespace and name.
        """

        if not isinstance( node.tag, str ):

            return False

        qname = etree.QName( node )

        return qname.localname == name and qname.namespace == INKRADIX_NAMESPACE


    def IsRadicalPieObject( self, group ):
        """
        Return True if the group contains exactly one <inkradix:radicalpie>
        element, which itself contains exactly one <inkradix:datav1> element.
        """

        radicalPieChildren = [
            child for child in group 
            if isinstance( child.tag, str ) and self.IsInkRadixElement (child, "radicalpie" )
        ]

        if len( radicalPieChildren ) != 1:
            return False

        radicalPieElem = radicalPieChildren[ 0 ]

        dataV1Children = [
            child for child in radicalPieElem
            if isinstance (child.tag, str ) and self.IsInkRadixElement( child, "datav1" )
        ]

        return len( dataV1Children ) == 1


    def FindEditingGroup( self ):

        """
        Find a selected group that is a RadicalPie object for editing.
    
        Returns:
            lxml.etree.Element | None: The group element or None if none selected.
        """

        selected = getattr( self.svg, "selection", getattr( self.svg, "selected", {} ) ) # To support older versions

        if not selected:

            return None

        for elem in selected.values( ):

            if elem.tag == inkex.addNS( 'g', 'svg' ) and self.IsRadicalPieObject( elem ):

                self.DebugMsg( "Editing existing RadicalPie group" )

                return elem


        self.msg( "Selected object is not an InkRadix or the equation is inside a group. Created a new one." )
            
        return None


    def ConvertXmlDataToRadicalPieComments( self, group ):

        """
        Convert InkRadix XML data elements into SVG comments.
    
        Parameters:
            group (lxml.etree.Element): Group containing InkRadix elements.
    
        Notes:
            Replaces <inkradix:radicalpie><datav1>text</datav1></inkradix:radicalpie>
            with <!--text--> comments.
        """

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

                    self.DebugMsg(  "ConverXmlDataToRadicalPieComments: "
                                    "Node had no parent during replacement." )


    def ConvertRadicalPieCommentsToXMLData( self, group ):

        """
        Convert RadicalPie comments back into InkRadix XML elements.
    
        Parameters:
            group (lxml.etree.Element): Group to process.
    
        Notes:
            Replaces <!--text--> comments with
            <inkradix:radicalpie><datav1>text</datav1></inkradix:radicalpie>.
        """

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

                    self.DebugMsg(  "ConvertRadicalPieCommentsToXMLData: "
                                    "Node had no parent during replacement." )


    def WriteInputSvg( self, svgFilePath, editingGroup ):

        """
        Write a temporary input SVG for RadicalPie.
    
        Parameters:
            svgFilePath (str): Path to write the SVG.
            editingGroup (lxml.etree.Element | None): Existing group to export, or None to use default.
        """

        if editingGroup is not None:

            newSvg = etree.Element( '{http://www.w3.org/2000/svg}svg' )
            newSvg.set( "version", "1.1" )

            groupCopy = copy.deepcopy( editingGroup )

            self.ConvertXmlDataToRadicalPieComments( groupCopy )

            newSvg.append( groupCopy )

            etree.ElementTree( newSvg ).write( svgFilePath, encoding="utf-8", xml_declaration=True )

        else:

            with open( svgFilePath, "w", encoding="utf-8" ) as f:

                f.write( SVG_DEFAULT_CONTENT )


    def RunRadicalPie( self, svgFilePath ):

        """
        Launch RadicalPie to edit the given SVG file.
    
        Parameters:
            svgFilePath (str): Path of the SVG file to edit.
        
        Returns:
            bool: True if the file changed, False if unchanged.
    
        Raises:
            inkex.AbortExtension: If RadicalPie is not found or fails.
        """

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

            self.DebugMsg("Hash comparison unavailable. Assuming file changed." )
            return True

        return beforeHash != afterHash



    def ParseOutputSvg( self, svgFilePath ):

        """
        Load an SVG file as an Inkex SVG document.
    
        Parameters:
            svgFilePath (str): Path to SVG file.
        
        Returns:
            inkex.SvgDocument: Parsed SVG object.
        """

        return inkex.load_svg( svgFilePath ) 
        

    def BuildGroupFromRoot( self, root ):

        """
        Build a new Inkex group from the root of an output SVG.
    
        Parameters:
            root (inkex.SvgDocument): Root SVG document from RadicalPie output.
        
        Returns:
            inkex.Group: New group containing output nodes with InkRadix data restored.
        """

        newGroup = inkex.Group( )
        newGroup.set ("id", self.svg.get_unique_id( "radicalpie-group" ) )
        newGroup.set(inkex.addNS( 'label', 'inkscape'), "RadicalPie Output" )
        newGroup.set(inkex.addNS( 'groupmode', 'inkscape'), 'group' )

        for node in root.getroot():
            newGroup.append( node )  

        self.ConvertRadicalPieCommentsToXMLData( newGroup )

        return newGroup


    def ClonePoseAnchored( self, oldGroup, newGroup ):

        """
        Copy the old group's anchored pivot pose to a new group.
    
        Parameters:
            oldGroup (inkex.Group): Original group with pose.
            newGroup (inkex.Group): New group generated by RadicalPie.
        
        Returns:
            bool: True if cloning succeeded, False otherwise.
        """

        if oldGroup is None or newGroup is None:
            return              
        
        # Old Pose
        try:

            oldPivotX = float(oldGroup.attrib.get(IS + "transform-center-x") or 0.0)
            oldPivotY = -float(oldGroup.attrib.get(IS + "transform-center-y") or 0.0)

        except Exception as e:

            raise inkex.AbortExtension( f"Error reading transform-center-x, or transform-center-y: {e}" )

        oldBBox         = oldGroup.bounding_box( )
        if oldBBox is None:

            return False

        oldLocalBBox    = GetLocalBoundingBox( oldGroup )

        if oldLocalBBox is None:

            return False

        # The new local bounding box generated by Radical Pie 
        layer = self.svg.get_current_layer()
        layer.append( newGroup )
        newLocalBBox = newGroup.bounding_box()
        layer.remove( newGroup )

        if newLocalBBox is None:

            return False

        # Map old pivot into local space, express it relative to the nearest anchor,
        # transfer that offset to the corresponding anchor in the new shape, then solve
        # translation so the reconstructed pivot matches the original in global space.
        # Details in: Resources/ClonePoseAnchored.svg
        T1              = inkex.Transform( oldGroup.attrib.get( 'transform', '' ) );
        T1inv           = -T1;
        c1g             = inkex.Vector2d( oldBBox.center_x, oldBBox.center_y )
        DeltaP1         = inkex.Vector2d( oldPivotX, oldPivotY)
        p1g             = c1g + DeltaP1
        P1l             = T1inv.apply_to_point( p1g )
        anchorName, a1l = GetNearestAnchor( P1l, oldLocalBBox )
        a2l             = GetAnchors( newLocalBBox )[ anchorName ]
        DeltaPl         = P1l - a1l
        c2l             = inkex.Vector2d( newLocalBBox.center_x, newLocalBBox.center_y )
        p2l             = DeltaPl + a2l 
        o               = p1g - T1.apply_to_point( p2l )

        if USE_AT_OPERATOR:

            T2 = inkex.Transform(f"translate({o.x},{o.y})") @ T1

        else:

            T2 = inkex.Transform(f"translate({o.x},{o.y})") * T1
        
        # Ideally, we would compute: c2g = T2.apply_to_point( c2l ), but inkscape 
        # recomputes the box from the transformed geometry. This can introduce small
        # shifts in the center due to stroke thickness or curve extrema. This subsequently
        # effects the corsshair location calculation.
        newGroup.set( 'transform', str( T2 ) )  
        layer.append( newGroup )
        finalGlobalBBox = newGroup.bounding_box()
        layer.remove( newGroup )
        c2g     = inkex.Vector2d( finalGlobalBBox.center_x, finalGlobalBBox.center_y )

        DeltaP2 = p1g - c2g

        newGroup.set( IS + "transform-center-x", str( DeltaP2.x ) )
        newGroup.set( IS + "transform-center-y", str( -DeltaP2.y ) )
        
        return True           


    def ApplyResultGroup( self, newGroup, editingGroup ):

        """
        Replace or append RadicalPie output into the current SVG.
    
        Parameters:
            newGroup (inkex.Group): New RadicalPie group.
            editingGroup (inkex.Group | None): Original group being edited, if any.
        """

        if editingGroup is not None:

            parent = editingGroup.getparent( )
            if parent is None:
            
                raise inkex.AbortExtension( "Editing group has no parent." )
                
            if 'transform' in newGroup.attrib:
            
                self.DebugMsg( "Warning: RadicalPie returned a transform, overriding it." )

            if not self.ClonePoseAnchored( editingGroup, newGroup ):

                self.DebugMsg( "ClonePoseAnchored failed. Original object preserved." )

            parent.replace( editingGroup, newGroup )

            self.DebugMsg( "Selection replaced with updated RadicalPie SVG." )
            
        else:

            layer = self.svg.get_current_layer( )
            layer.append( newGroup )

            self.DebugMsg( "New RadicalPie SVG added." )



    def PrepareTempFile( self, editingGroup ):

        """
        Create a temporary SVG file for RadicalPie input.
    
        Parameters:
            editingGroup (inkex.Group | None): Group to export, or None.
        
        Returns:
            str: Path to temporary SVG file.
        """

        tmpFile = tempfile.NamedTemporaryFile( suffix=".svg", delete=False )
        svgFilePath = tmpFile.name
        tmpFile.close( )

        self.WriteInputSvg( svgFilePath, editingGroup )

        return svgFilePath


    def ApplyChanges( self, changed, editingGroup, svgFilePath ):

        """
        Apply changes from RadicalPie output back into the SVG document.
    
        Parameters:
            changed (bool): Whether RadicalPie modified the SVG.
            editingGroup (inkex.Group | None): Original group being edited, if any.
            svgFilePath (str): Path to RadicalPie output SVG.
        """

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

        """
        Main entry point for the InkRadix extension.
    
        Workflow:
            1. Ensure Windows platform.
            2. Detect editing group.
            3. Prepare temp SVG file.
            4. Run RadicalPie.
            5. Apply output back into SVG.
    
        Raises:
            inkex.AbortExtension: For any error including RadicalPie not found, XML parsing errors, or unexpected exceptions.
    """

        if sys.platform != "win32":

            raise inkex.AbortExtension(
                "InkRadix extension only works on Windows RadicalPie integration requires a "
                "Windows system."
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
