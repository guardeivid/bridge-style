import os
import json
import zipfile
from qgiscommons2.files import tempFilenameInTempFolder
from .expressions import walkExpression, UnsupportedExpressionException

try:
    from qgis.core import *
except:
    pass

_usedIcons = {}
_warnings = []

def layerAsGeostyler(layer):
    global _usedIcons
    _usedIcons = {}
    global _warnings
    _warnings = []
    geostyler = processLayer(layer)
    return geostyler, _usedIcons, _warnings

def processLayer(layer):
    if layer.type() == layer.VectorLayer:
        rules = []
        renderer = layer.renderer()
        if not isinstance(renderer, QgsRuleBasedRenderer):
            renderer = QgsRuleBasedRenderer.convertFromRenderer(renderer)
        if renderer is None:
            pass #show error
        for rule in renderer.rootRule().children():
            rules.append(processRule(rule))
        labelingSymbolizer = processLabeling(layer)
        if labelingSymbolizer is not None:
            rules.append(labelingSymbolizer)
        return  {"name": layer.name(), "rules": rules}
    elif layer.type() == layer.RasterLayer:
        rules = [{"name": layer.name(), "symbolizers": [rasterSymbolizer(layer)]}]
        return  {"name": layer.name(), "rules": rules}

def rasterSymbolizer(layer):    
    renderer = layer.renderer()    
    symbolizer = {"kind": "Raster", "opacity": renderer.opacity(),
                 "channelSelection": channelSelection(renderer)}
    colMap = colorMap(renderer)
    if colMap:
        symbolizer["colorMap"] = colMap
    return symbolizer

def channelSelection(renderer):
    if isinstance(renderer, QgsSingleBandGrayRenderer):
        return {"grayChannel": {"sourceChannelName": str(renderer.grayBand())}}
    elif isinstance(renderer, (QgsSingleBandPseudoColorRenderer, QgsPalettedRasterRenderer)):
         return {"grayChannel": {"sourceChannelName": str(renderer.band())}}
    elif isinstance(renderer, QgsMultiBandColorRenderer):
        bands = renderer.usesBands()
        channels = {}
        if len(bands) > 0:
            channels["redChannel"] = {"sourceChannelName": str(bands[0])}
        if len(bands) > 1:
            channels["greenChannel"] = {"sourceChannelName": str(bands[1])}
        if len(bands) > 2:
            channels["blueChannel"] = {"sourceChannelName": str(bands[2])}
        return channels
    else:
        _warnings.append("Unsupported raster renderer class: '%s'" % str(renderer))
        return None

def colorMap(renderer):
    colMap = {}
    mapEntries = []
    if isinstance(renderer, QgsSingleBandGrayRenderer):
        colMap["type"] = "ramp"
        entries = renderer.legendSymbologyItems()
        for entry in entries:
            mapEntries.append({"color": entry[1].name() , "quantity": float(entry[0]),
                            "opacity": entry[1].alphaF(), "label": entry[0]})
    elif isinstance(renderer, QgsSingleBandPseudoColorRenderer):
        rampType = "ramp"
        shader = renderer.shader().rasterShaderFunction()
        colorRampType = shader.colorRampType   
        if colorRampType == QgsColorRampShader.Exact:
            rampType = "values"
        elif colorRampType == QgsColorRampShader.Discrete:
            rampType = "intervals"
        colMap["type"] = rampType
        items = shader.colorRampItemList()
        for item in items:
            mapEntries.append({"color": item.color.name() , "quantity": item.value,
                            "label": item.label, "opacity": item.color.alphaF()})
    elif isinstance(renderer, QgsPalettedRasterRenderer):
        colMap["type"] = "values"
        classes = renderer.classes()
        for c in classes:
            mapEntries.append({"color": c.color.name() , "quantity": c.value,
                            "label": c.label, "opacity": c.color.alphaF()})
    elif isinstance(renderer, QgsMultiBandColorRenderer):
        return None
    else:
        _warnings.append("Unsupported raster renderer class: '%s'" % str(renderer))
        return None

    colMap["extended"] = True
    if mapEntries is not None:
        colMap["colorMapEntries"] = mapEntries
    return colMap

quadOffset = ["top", "top-right", "left", "center", "right", "bottom-left", "bottom", "bottom-right"]

def processLabeling(layer):
    if not layer.labelsEnabled():
        return None
    labeling = layer.labeling()
    if labeling is None:
        return None

    if not isinstance(labeling, QgsVectorLayerSimpleLabeling):
        _warnings.append("Unsupported labeling class: '%s'" % str(labeling))
        return None
    symbolizer = {"Kind": "Text"}
    settings = labeling.settings()
    textFormat = settings.format()    
    size = _labelingProperty(settings, textFormat, "size", QgsPalLayerSettings.Size)
    color = textFormat.color().name()
    font = textFormat.font().family()
    buff = textFormat.buffer()
    if buff.enabled():
        haloColor = buff.color().name()
        haloSize = _labelingProperty(settings, buff, "size", QgsPalLayerSettings.BufferSize)
        symbolizer.update({"haloColor": haloColor,
                            "haloSize": haloSize})
    anchor = quadOffset[settings.quadOffset]
    offsetX = _labelingProperty(settings, None, "xOffset")
    offsetY = _labelingProperty(settings, None, "yOffset")
    exp = settings.getLabelExpression()
    label = walkExpression(exp.rootNode())
    symbolizer.update({"color": color,
                        "offset": [offsetX, offsetY],
                        "font": font,
                        "anchor": anchor,
                        "label": label,
                        "size": size})
    return {"symbolizers": symbolizer}

def processRule(rule):
    symbolizers = _createSymbolizers(rule.symbol().clone())
    name = rule.label()
    ruledef = {"name": name,
            "symbolizers": symbolizers}
    if not(rule.isElse()):
        filt = processExpression(rule.filterExpression())
        if filt is not None:
            ruledef["filter"] = filt
    if rule.dependsOnScale():
        scale = processRuleScale(rule)
        ruledef["scaleDenominator"] = scale
    return ruledef

def processRuleScale(rule):
    return {"min": rule.minimumScale(),
            "max": rule.maximumScale()}

def processExpression(expstr):
    try:
        if expstr:
            exp = QgsExpression(expstr)
            return walkExpression(exp.rootNode())
        else:
            return None
    except UnsupportedExpressionException as e:
        _warnings.append(str(e))
        return None

def _cast(v):
    if isinstance(v, basestring):
        try:
            return float(v)
        except:
            return v
    else:
        return v

MM2PIXEL = 3.7795275591

def _handleUnits(value, units):
    if str(value) in ["0", "0.0"]:
        return 1 #hairline width
    if units == "MM":
        if isinstance(value, list):
            return ["Mul", MM2PIXEL, value]
        else:
            return float(value) * MM2PIXEL
    elif units == "RenderMetersInMapUnits":
        if isinstance(value, list):
            _warning.append("Cannot render in map units when using a data-defined size value: '%s'" % str(value))
            return value
        else:
            return str(value) + "m"
    elif units == "Pixel":
        return value
    else:
        _warning.append("Unsupported units: '%s'" % units)
        return value

def _labelingProperty(settings, obj, name, propertyConstant=-1):
    ddProps = settings.dataDefinedProperties()
    if propertyConstant in ddProps.propertyKeys():
        v = processExpression(ddProps.property(propertyConstant).asExpression()) or ""        
    else:
        v = getattr(obj or settings, name)
        try:
            v = v()
        except:
            pass

    return _cast(v)

def _symbolProperty(symbolLayer, name, propertyConstant=-1):
    ddProps = symbolLayer.dataDefinedProperties()
    if propertyConstant in ddProps.propertyKeys():
        v = processExpression(ddProps.property(propertyConstant).asExpression()) or ""        
    else:
        v = symbolLayer.properties()[name]
    
    units = symbolLayer.properties().get(name + "_unit")
    if units is not None:
        v = _handleUnits(v, units)
    return _cast(v)

def _toHexColor(color):
    try:
        r,g,b,a = str(color).split(",")
        return '#%02x%02x%02x' % (int(r), int(g), int(b))
    except:
        return color
        
def _createSymbolizers(symbol):
    opacity = symbol.opacity()
    symbolizers = []    
    for sl in symbol.symbolLayers():
        symbolizer = _createSymbolizer(sl, opacity)        
        if symbolizer is not None:
            if isinstance(symbolizer, list):
                symbolizers.extend(symbolizer)
            else:
                symbolizers.append(symbolizer)

    return symbolizers

def _createSymbolizer(sl, opacity):
    symbolizer = None
    if isinstance(sl, QgsSimpleMarkerSymbolLayer):
        symbolizer = _simpleMarkerSymbolizer(sl, opacity)            
    elif isinstance(sl, QgsSimpleLineSymbolLayer):
        symbolizer = _lineSymbolizer(sl, opacity)
    elif isinstance(sl, QgsMarkerLineSymbolLayer):
        symbolizer = _markerLineSymbolizer(sl, opacity)   
    elif isinstance(sl, QgsSimpleFillSymbolLayer):
        symbolizer = _simpleFillSymbolizer(sl, opacity)
    elif isinstance(sl, QgsPointPatternFillSymbolLayer):
        symbolizer = _pointPatternFillSymbolizer(sl, opacity)       
    elif isinstance(sl, QgsSvgMarkerSymbolLayer):
        symbolizer = _svgMarkerSymbolizer(sl, opacity)
    elif isinstance(sl, QgsRasterMarkerSymbolLayer):
        symbolizer = _rasterImageMarkerSymbolizer(sl, opacity)      
    elif isinstance(sl, QgsGeometryGeneratorSymbolLayer):
        symbolizer = _geomGeneratorSymbolizer(sl, opacity)
    elif isinstance(sl, QgsFontMarkerSymbolLayer):
        symbolizer = _fontMarkerSymbolizer(sl, opacity)

    if symbolizer is None:
        _warning.append("Symbol layer type not supported: '%s'" % type(sl))
    return symbolizer


def _fontMarkerSymbolizer(sl, opacity):
    color = _toHexColor(sl.properties()["color"])
    fontFamily = _symbolProperty(sl, "font")
    character = _symbolProperty(sl, "chr", QgsSymbolLayer.PropertyCharacter)
    size = _symbolProperty(sl, "size", QgsSymbolLayer.PropertySize)

    symbolizer = {"kind": "Text",
                    "size": size,
                    "label": character,
                    "font": fontFamily,
                    "color": color}    
    return symbolizer

def _lineSymbolizer(sl, opacity):
    props = sl.properties()
    color = _toHexColor(props["line_color"])
    width = _symbolProperty(sl, "line_width", QgsSymbolLayer.PropertyStrokeWidth)    
    lineStyle = _symbolProperty(sl, "line_style", QgsSymbolLayer.PropertyStrokeStyle)
    cap = _symbolProperty(sl, "capstyle", QgsSymbolLayer.PropertyCapStyle)
    cap = "butt" if cap == "flat" else cap
    join = _symbolProperty(sl, "joinstyle", QgsSymbolLayer.PropertyJoinStyle)
    offset = _symbolProperty(sl, "offset", QgsSymbolLayer.PropertyOffset)    
    symbolizer = {"kind": "Line",
                    "color": color,
                    "opacity": opacity,
                    "width": width,
                    "perpendicularOffset": offset,
                    "cap": cap,
                    "join": join
                    }
    if lineStyle != "solid":
        symbolizer["dasharray"] = "5 2"
    return symbolizer

def _markerLineSymbolizer(sl, opacity):
    offset = _symbolProperty(sl, "offset", QgsSymbolLayer.PropertyOffset) 
    symbolizer = {"kind": "Line",                
                    "opacity": opacity,
                    "perpendicularOffset": offset}
    subSymbolizers = []
    for subsl in sl.subSymbol().symbolLayers():       
        subSymbolizer = _createSymbolizer(subsl, 1)
        if subSymbolizers is not None:
            subSymbolizers.append(subSymbolizer)
    if subSymbolizers:
        interval = _symbolProperty(sl, "interval", QgsSymbolLayer.PropertyInterval)
        offsetAlong = _symbolProperty(sl, "offset_along_line", QgsSymbolLayer.PropertyOffsetAlongLine)
        symbolizer["graphicStroke"] = subSymbolizers
        symbolizer["graphicStrokeInterval"] = interval
        symbolizer["graphicStrokeOffset"] = offsetAlong

    return symbolizer    

def _geomGeneratorSymbolizer(sl, opacity):
    subSymbol = sl.subSymbol()
    symbolizers = _createSymbolizers(subSymbol)
    geomExp = sl.geometryExpression()    
    geom = processExpression(geomExp)
    for symbolizer in symbolizers:
        symbolizer["Geometry"] = geom
    return symbolizers

def _svgMarkerSymbolizer(sl, opacity):
    marker = _basePointSimbolizer(sl, opacity)
    color = _toHexColor(sl.properties()["color"])
    marker["color"] = color
    svg = _markGraphic(sl)    
    marker.update(svg)
    return marker

def _rasterImageMarkerSymbolizer(sl, opacity):
    marker = _basePointSimbolizer(sl, opacity)
    img = _iconGraphic(sl)
    marker.update(img)
    return marker  

def _simpleMarkerSymbolizer(sl, opacity):
    marker = _basePointSimbolizer(sl, opacity)
    mark = _markGraphic(sl)
    marker.update(mark)    
    return marker

def _basePointSimbolizer(sl, opacity):
    props = sl.properties()        
    rotation = _symbolProperty(sl, "angle", QgsSymbolLayer.PropertyAngle)
    x, y = sl.offset().x(), sl.offset().y()
    
    symbolizer =  {
        "opacity": opacity,
        "rotate": rotation
        } 

    if x or y:
        exp = "translate($geometry, %s,%s)" % (str(x), str(y))        
        symbolizer["geometry"] = processExpression(exp)

    return symbolizer

wknReplacements = {"regular_star":"star",
               "cross2": "x",
               "equilateral_triangle": "triangle",
               "rectangle": "square",
               "filled_arrowhead": "ttf://Webdings#0x34",
               "line": "shape://vertline",
               "arrow": "ttf://Wingdings#0xE9",
               "diamond": "ttf://Wingdings#0x75",
                "horline":"shape://horline",
               "vertline":"shape://vertline",
               "cross":"shape://plus",
               "slash":"shape://slash",
               "backslash":"shape://backslash",
               "x": "shape://times"}

def _markGraphic(sl):
    props = sl.properties()
    size = _symbolProperty(sl, "size", QgsSymbolLayer.PropertySize)
    color = _toHexColor(props["color"])
    outlineColor = _toHexColor(props["outline_color"])
    outlineWidth = _symbolProperty(sl, "outline_width", QgsSymbolLayer.PropertyStrokeWidth)    
    try:
        path = sl.path()
        global _usedIcons
        _usedIcons[sl.path()] = sl
        name = "file://" + os.path.basename(path)
        outlineStyle = "solid"
        size = _symbolProperty(sl, "size", QgsSymbolLayer.PropertyWidth)
    except:
        name = props["name"]
        name = wknReplacements.get(name, name)
        outlineStyle = _symbolProperty(sl, "outline_style", QgsSymbolLayer.PropertyStrokeStyle)
        if outlineStyle == "no":
            outlineWidth = 0

    mark = {"kind": "Mark",
            "color": color,
            "wellKnownName": name,
            "size": size,
            "strokeColor": outlineColor,
            "strokeWidth": outlineWidth            
            } 
    if outlineStyle not in ["solid", "no"]:
        mark["strokeDasharray"] = "5 2"

    return mark

FIXED_PATTERN_SIZE = 10

def _markFillPattern(shape, color):    
    shape = wknReplacements.get(shape, shape)
    return {"kind": "Mark",
            "color": color,
            "wellKnownName": shape,
            "size": FIXED_PATTERN_SIZE,
            "strokeColor": color,
            "strokeWidth": 1
            } 

def _iconGraphic(sl, color=None):    
    global _usedIcons
    _usedIcons[sl.path()] = sl
    path = os.path.basename(sl.path())
    size = _symbolProperty(sl, "size", QgsSymbolLayer.PropertySize)
    return {"kind": "Icon",
            "color": color,
            "image": path,
            "size": size,
            }  

def _baseFillSymbolizer(sl, opacity):
    return {"kind": "Fill",
            "opacity": opacity}

def _pointPatternFillSymbolizer(sl, opacity):    
    symbolizer = _baseFillSymbolizer(sl, opacity)
    subSymbolizers = []
    for subsl in sl.subSymbol().symbolLayers():       
        subSymbolizer = _createSymbolizer(subsl, 1)
        if subSymbolizers is not None:
            subSymbolizers.append(subSymbolizer)
    if subSymbolizers:
        distancex = _symbolProperty(sl, "distance_x", QgsSymbolLayer.PropertyDistanceX)
        distancey = _symbolProperty(sl, "distance_y", QgsSymbolLayer.PropertyDistanceY)
        symbolizer["graphicFill"] = subSymbolizers
        distancex = ["Div", distancex, 2] if isinstance(distancex, list) else distancex / 2.0
        distancey = ["Div", distancex, 2] if isinstance(distancey, list) else distancey / 2.0
        symbolizer["graphicFillMarginX"] = distancex
        symbolizer["graphicFillMarginY"] = distancey

    return symbolizer

patternNamesReplacement = {"horizontal": "horline",
                            "vertical": "vertline",
                            "cross": "x"} #TODO

def _simpleFillSymbolizer(sl, opacity):
    props = sl.properties()
    style = props["style"]
    
    symbolizer = _baseFillSymbolizer(sl, opacity)

    if style != "no":
        color =  _toHexColor(props["color"])               
        if style == "solid":
            symbolizer["color"] = color            
        else:
            style = patternNamesReplacement.get(style, style)
            marker = _markFillPattern(style, color)
            symbolizer["graphicFill"] = [marker]
            symbolizer["graphicFillDistanceX"] = FIXED_PATTERN_SIZE / 2.0
            symbolizer["graphicFillDistanceY"] = FIXED_PATTERN_SIZE / 2.0

    outlineColor =  _toHexColor(props["outline_color"])
    outlineStyle = _symbolProperty(sl, "outline_style", QgsSymbolLayer.PropertyStrokeStyle)
    if outlineStyle != "no":
        outlineWidth = _symbolProperty(sl, "outline_width", QgsSymbolLayer.PropertyStrokeWidth)
        symbolizer.update({"outlineColor": outlineColor,
                            "outlineWidth": outlineWidth})
    if outlineStyle not in ["solid", "no"]:
        symbolizer["outlineDasharray"] ="5 2"

    x, y = sl.offset().x(), sl.offset().y()    
    if x or y:
        symbolizer["geometry"] = processExpression("translate(%s,%s)" % (str(x), str(y)))

    return symbolizer

   
