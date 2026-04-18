# InkRadix v 1.1.0
# An Inkscape extension for editable Radical Pie Equations
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

import sys

if sys.platform != "win32":

    import inkex

    raise inkex.AbortExtension(
        "This extension is designed to work only on Windows, as it relies on the Windows registry for configuration."
    )

import os
import re
import copy
import winreg
import hashlib
import tempfile
import subprocess
import inkex

from lxml import etree


DEBUG = True


SVG_DEFAULT_CONTENT   = """<svg width="6pt" height="9pt" viewBox="0 -9 6 9" version="1.1" xmlns="http://www.w3.org/2000/svg"><desc>Radical Pie Equation</desc><!--D{} Gr { Bg {}}--></svg>"""
FALLBACK_RP_EXE_PATH1 = r"C:\Program Files\RadicalPie\RadicalPie.exe"
FALLBACK_RP_EXE_PATH2 = r"D:\Program Files\RadicalPie\RadicalPie.exe"

INKRADIX_NAMESPACE    = "https://github.com/nasosi/InkRadix/ns"
INKSCAPE_NAMESPACE    = "http://www.inkscape.org/namespaces/inkscape"
IR                    = f"{{{INKRADIX_NAMESPACE}}}"
IS                    = f"{{{INKSCAPE_NAMESPACE}}}"

etree.register_namespace( "inkradix", INKRADIX_NAMESPACE )

USE_AT_OPERATOR = hasattr( inkex.Transform, "__matmul__" )

if USE_AT_OPERATOR:

    def Mult( A, B ):

        return A @ B

else:

    # Older inkex versions
    def Mult( A, B ):

        return A * B


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
        
    return bBox

def SelectionIterable( selection ):
    """
    Get an iterable object from a selection to support multiple versions of inkex

    Parameters:
        
        selection: an inkex selection or selected
    """

    if selection is None:

        return []

    if hasattr( selection, "values" ):

        return selection.values()

    return selection


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
        tuple[str, inkex.Vector2d]: (nearestAnchorName, nearestAnchorPoint)
    """

    nearestAnchorName, nearestAnchorPoint = min(
        GetAnchors( bBox ).items(),
        key = lambda kv: ( kv[ 1 ] - point ).length
    )
    return nearestAnchorName, nearestAnchorPoint


class InkRadix( inkex.EffectExtension ):
    """
       The main extension class.
    """

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

        except Exception:

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
        if not hasattr( group, "tag" ) or group.tag != inkex.addNS( 'g', 'svg' ):

            return False

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


    def GetSelectionAndEditingGroup( self ):
        """
        Find a selected group that is a RadicalPie object for editing.
    
        Returns:
            tuple[ inkex.selection, lxml.etree.Element | None ]: ( 
                The selection if something was selected, and an rmpty ElementList if not
                The Radical Pie group element or None if no Radical Pie group is selected 
                )
        """

        selection = getattr( self.svg, "selection", getattr( self.svg, "selected", { } ) ) # To support older versions

        for elem in SelectionIterable( selection ):

            if self.IsRadicalPieObject( elem ):

                self.DebugMsg( "Editing existing RadicalPie group" )

                return selection, elem
            
        return selection, None


    def ConvertXmlDataToRadicalPieCommentBlock( self, group ):
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

                dataElem = None
                for child in node:

                    if self.IsInkRadixElement(child, "datav1"):

                        dataElem = child
                        break

                text = dataElem.text if dataElem is not None else ""

                comment = etree.Comment( text or "" )

                parent = node.getparent( )
                if parent is not None:

                    parent.replace( node, comment )

                else:

                    self.DebugMsg( "ConvertXmlDataToRadicalPieComments: Node had no parent during replacement." )


    def ConvertFirstRadicalPieCommentBlockToXMLData( self, group ):
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

                parent = node.getparent( )
                if parent is None:

                    raise inkex.AbortExtension( f"InkRadix: ConvertRadicalPieCommentsToXMLData: Node had no parent during replacement." )

                rpElem = etree.Element( IR + "radicalpie" )
                dataElem = etree.SubElement( rpElem, IR + "datav1" )
                dataElem.text = text

                parent.replace( node, rpElem )

                return rpElem               

        raise inkex.AbortExtension( f"ConvertRadicalPieCommentsToXMLData: Group has no nodes, or Radical Pie comments." )


    def WriteInputSvg( self, svgFilePath, editingGroup ):
        """
        Write a temporary input SVG for RadicalPie.
    
        Parameters:
            svgFilePath (str): Path to write the SVG.
            editingGroup (lxml.etree.Element | None): Existing group to export, or None to use default.
        """

        if editingGroup is None:

            with open( svgFilePath, "w", encoding = "utf-8" ) as f:

                f.write( SVG_DEFAULT_CONTENT )

            return

        newSvg = etree.Element( '{http://www.w3.org/2000/svg}svg' )
        newSvg.set( "version", "1.1" )

        groupCopy = copy.deepcopy( editingGroup )

        self.ConvertXmlDataToRadicalPieCommentBlock( groupCopy )

        newSvg.append( groupCopy )

        etree.ElementTree( newSvg ).write( svgFilePath, encoding="utf-8", xml_declaration=True )


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
        Build a new Inkex group from the root of an output SVG,
        applying the root SVG's viewBox scaling so geometry matches
        its intended rendered size.
        
        Parameters:
            root (inkex.SvgDocument): Root SVG document from RadicalPie output.
        
        Returns:
            inkex.Group: New group containing output nodes with InkRadix data restored.
        """

        svgRoot = root.getroot( )

        newGroup = inkex.Group( )
        newGroup.set( "id", self.svg.get_unique_id( "radicalpie-group" ) )
        newGroup.set( inkex.addNS( 'label', 'inkscape' ), "RadicalPie Output" )
        newGroup.set( inkex.addNS( 'groupmode', 'inkscape' ), 'group' )

        for node in svgRoot:

            newGroup.append( copy.deepcopy( node ) )

        rpElem = self.ConvertFirstRadicalPieCommentBlockToXMLData( newGroup )

        viewBoxStr = svgRoot.get( "viewBox" )
        widthStr   = svgRoot.get( "width" )
        heightStr  = svgRoot.get( "height" )

        if viewBoxStr and widthStr and heightStr:

            try:

                viewBoxElements = re.split(r"[,\s]+", viewBoxStr.strip())

                try:
                    vbX, vbY, vbW, vbH = map( float, viewBoxElements )

                except Exception:

                    raise ValueError( f"Invalid viewBox format: {viewBoxStr}" )


                widthInDocumentUnits  = self.svg.unittouu( widthStr )
                heightInDocumentUnits = self.svg.unittouu( heightStr )

                self.msg( vbW )
                self.msg( widthStr )

                if vbW != 0 and vbH != 0:

                    scaleX = widthInDocumentUnits / vbW
                    scaleY = heightInDocumentUnits / vbH

                    T = inkex.Transform( )
                    T.add_translate( -vbX * scaleX, -vbY * scaleY )
                    T.add_scale( scaleX, scaleY )

                    newGroup.set( "transform", str( T ) )

                    # Create a line from (0,0) to (width,0), transformed by T
                    line = inkex.Line()
                    line.set('x1', vbX )
                    line.set('y1', 0)
                    line.set('x2', str( vbX + vbW ) )
                    line.set('y2', 0)
                    line.set('style', 'stroke:#000000;stroke-width:0.05')
                    newGroup.append(line)

                    # We are not using the following, but if Inkscape or Radical Pie ever change units,
                    # we will be able to support documents saved in older versions
                    if rpElem is not None:

                        vbElem = etree.SubElement( rpElem, IR + "rPieViewBox")
                        wElem  = etree.SubElement( rpElem, IR + "rPieWidth")
                        hElem  = etree.SubElement( rpElem, IR + "rPieHeight" )

                        vbElem.text = viewBoxStr
                        wElem.text = widthStr
                        hElem.text = heightStr

            except Exception as e:

                self.DebugMsg( f"ViewBox transform failed: {e}" )

        return newGroup


    def MoveToSelectionCenter( self, selection, group ):

        """
        Move `group` so its bounding box center matches the center of the aabb of the `selection` elements.

        Parameters :
            selection (inkex.elements._selected.ElementList): Collection of selected elements.
            group (inkex.elements.Group):  Group to reposition.
        """

        selectionBBox = None

        for elem in SelectionIterable( selection ):

            if not hasattr( elem, "tag" ):

                continue

            elemBBox = elem.bounding_box( )
            if elemBBox is None:

                continue

            if selectionBBox is None:

                selectionBBox = elemBBox

            else:

                selectionBBox += elemBBox

        if selectionBBox is None:

            return

        layer = self.svg.get_current_layer( )
        layer.append( group )
        groupBBox = group.bounding_box( )
        layer.remove( group )

        if groupBBox is None:

            return

        DeltaX = selectionBBox.center_x - groupBBox.center_x
        DeltaY = selectionBBox.center_y - groupBBox.center_y

        group.transform = Mult( inkex.Transform( f"translate({DeltaX}, {DeltaY})"), group.transform )


    def CloneAnchoredPose( self, oldGroup, newGroup ):
        """
        Copy the old group's anchored pivot pose to a new group.
    
        Parameters:
            oldGroup (inkex.Group): Original group with pose.
            newGroup (inkex.Group): New group generated by RadicalPie.
        
        Returns:
            bool: True if cloning succeeded, False otherwise.
        """

        if oldGroup is None or newGroup is None:

            return True             
        
        try:

            oldPivotX =  float(oldGroup.attrib.get( IS + "transform-center-x" ) or 0.0 )
            oldPivotY = -float(oldGroup.attrib.get( IS + "transform-center-y" ) or 0.0 )

        except Exception as e:

            raise inkex.AbortExtension( f"Error reading transform-center-x, or transform-center-y: {e}" )

        oldBBox = oldGroup.bounding_box( )
        if oldBBox is None:

            return False

        oldLocalBBox    = GetLocalBoundingBox( oldGroup )

        if oldLocalBBox is None:

            return False

        # The new local bounding box generated by Radical Pie 
        # NOTE: Resetting newGroup.transform assumes Inkscape document units are fixed (and not likely to ever change).
        # If that ever happens, the scaling from BuildGroupFromRoot may become invalid. ViewBox, width, and height from 
        # RPie are already stored for potential future compatibility.
        layer = self.svg.get_current_layer( )
        layer.append( newGroup )
        newGroup.transform = inkex.Transform( ) 
        newLocalBBox = newGroup.bounding_box( )
        layer.remove( newGroup )

        if newLocalBBox is None:

            return False

        # Map old pivot into local space, fint the nearest local anchor of the old equation, find the corresponding 
        # anchor in the new group, then solve translation so the new group's anchor matches the original in global 
        # space. Details in: Resources/CloneAnchoredPose.svg
        T1              = inkex.Transform( oldGroup.attrib.get( 'transform', '' ) )
        T1inv           = -T1
        c1g             = inkex.Vector2d( oldBBox.center_x, oldBBox.center_y )
        DeltaP1         = inkex.Vector2d( oldPivotX, oldPivotY)
        p1g             = c1g + DeltaP1
        P1l             = T1inv.apply_to_point( p1g )
        anchorName, a1l = GetNearestAnchor( P1l, oldLocalBBox )
        a2l             = GetAnchors( newLocalBBox )[ anchorName ]
        # Below, we avoid T1*(a1l-a2l), because the inkex transform applies to a point and 
        # not to a vector
        o               = T1.apply_to_point( a1l ) - T1.apply_to_point( a2l ) 
        T2              = Mult( inkex.Transform( f"translate({o.x},{o.y})" ), T1 )
        
        # We cannot compute
        # c2l = inkex.Vector2d( newLocalBBox.center_x, newLocalBBox.center_y )
        # c2g = T2.apply_to_point( c2l ), 
        # because the aabb that results is not in general the same with the
        # typographic bounding box. 
        newGroup.set( 'transform', str( T2 ) )  
        layer.append( newGroup )
        finalGlobalBBox = newGroup.bounding_box()
        layer.remove( newGroup )
        c2g     = inkex.Vector2d( finalGlobalBBox.center_x, finalGlobalBBox.center_y )

        DeltaP2 = p1g - c2g

        newGroup.set( IS + "transform-center-x", str(  DeltaP2.x ) )
        newGroup.set( IS + "transform-center-y", str( -DeltaP2.y ) )
        
        return True           


    def ApplyResultGroup( self, selection, newGroup, editingGroup ):
        """
        Replace or append RadicalPie output into the current SVG.
    
        Parameters:
            newGroup (inkex.Group): New RadicalPie group.
            editingGroup (inkex.Group | None): Original group being edited, if any.
        """

        if editingGroup is None:

            self.MoveToSelectionCenter( selection, newGroup )

            layer = self.svg.get_current_layer( )
            layer.append( newGroup )

            self.DebugMsg( "New RadicalPie SVG added." )
            return

        parent = editingGroup.getparent( )
        if parent is None:
            
            raise inkex.AbortExtension( "Editing group has no parent." )
                
        if not self.CloneAnchoredPose( editingGroup, newGroup ):

            self.DebugMsg( "CloneAnchoredPose failed. Original object preserved." )

        parent.replace( editingGroup, newGroup )

        self.DebugMsg( "Selection replaced with updated RadicalPie SVG." )
            

    def PrepareTempFile( self, editingGroup ):
        """
        Create a temporary SVG file for RadicalPie input.
    
        Parameters:
            editingGroup (inkex.Group | None): Group to export, or None.
        
        Returns:
            str: Path to temporary SVG file.
        """

        tmpFile = tempfile.NamedTemporaryFile( suffix = ".svg", delete = False )
        svgFilePath = tmpFile.name
        tmpFile.close( )

        self.WriteInputSvg( svgFilePath, editingGroup )

        return svgFilePath


    def ApplyChanges( self, selection, changed, editingGroup, svgFilePath ):
        """
        Apply changes from RadicalPie output back into the SVG document.
    
        Parameters:
            selection(inkex.elements._selected.ElementList): The user selection.
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

        self.ApplyResultGroup( selection, newGroup, editingGroup )

    def effect( self ):
        """
        Main entry point for the InkRadix extension.
    
        Raises:
            inkex.AbortExtension: For any error including RadicalPie not found, XML parsing errors, or unexpected exceptions.
        """
        svgFilePath = None

        try:

            selection, editingGroup = self.GetSelectionAndEditingGroup( )
            svgFilePath             = self.PrepareTempFile( editingGroup )
            svgFileChanged          = self.RunRadicalPie( svgFilePath )

            self.ApplyChanges( selection, svgFileChanged, editingGroup, svgFilePath )

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
                            
                        os.remove( svgFilePath )

                except Exception:

                    pass


if __name__ == '__main__':

    InkRadix( ).run( )
