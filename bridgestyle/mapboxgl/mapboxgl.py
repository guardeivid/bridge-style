import json

_warnings = []

def processLayer(geostyler):
	global _warnings
	_warnings = []
    layers = processLayer(geostyler)
    obj = {
        "version": 8,
        "name": geostyler["name"],
        "glyphs": "mapbox://fonts/mapbox/{fontstack}/{range}.pbf",
        "sources": {geostyler["name"]: {"TODO:Configure this!!!",""}}
        "layers": layers,
        "sprite": "spriteSheet",
    }
    
    obj["sprite"] = "spriteSheet"
    
    return json.dumps(obj), _warnings

def _toZoomLevel(scale):
    return int(math.log(1000000000 / scale, 2))

def processLayer(layer):
    allLayers = []
    
    for rule in geostyler["rules"]:
        layers = processRule(rule, layer["name"])
        allLayers.append(layers)

    return allLayers

def processRule(rule, source):
	filt = convertExpression(rule.get("filter", None))
	minzoom = None
	maxzoom = None
	if "scaleDenominator" in rule:
        scale = rule["scaleDenominator"]
        if "max" in scale:
            maxzoom =  = _toZoomLevel(scale["max"])
        if "min" in scale:
            minzoom =  = _toZoomLevel(scale["min"])            
    name = rule.get("name", "rule")
	layers = [processSymbolizer(s) for s in rule["symbolizers"]]
	for i, lay in enumerate(layers):
		if filt is not None:
			lay["filter"] = filt
		lay["source"] = source
		lay["id"] = name + ":" + str(i)
		if minzoom is not None:
			lay["minzoom"] = minzoom
		if maxzoom is not None:
			lay["maxzoom"] = maxzoom
	return layers

operators = {"PropertyName", "get"} #TODO

def convertExpression(exp):
	if exp is None:
        return None
    if isinstance(exp, list):
        exp[0] = operators.get(exp[0], exp[0])
    return exp

def processSymbolizer(sl):
    symbolizerType = sl["kind"]
    if symbolizerType == "Icon":
        symbolizer = _iconSymbolizer(sl)
    if symbolizerType == "Line":
        symbolizer = _lineSymbolizer(sl)            
    if symbolizerType == "Fill":
        symbolizer = _fillSymbolizer(sl)
    if symbolizerType == "Mark":
        symbolizer = _markSymbolizer(sl)
    if symbolizerType == "Text":
        symbolizer = _textSymbolizer(sl)
    if symbolizerType == "Raster":
        symbolizer = _rasterSymbolizer(sl)        
    
    geom = _geometryFromSymbolizer(sl)
    if geom is not None:
        _warnings.append("Derived geometries are not supported in mapbox gl")

    return symbolizer

def _symbolProperty(sl, name):
    if name in sl:        
        return convertExpression(sl[name])      
    else:
        return None

def _textSymbolizer(sl):
	layout = {}
    paint = {} 
	color = _symbolProperty(sl, "color")
    fontFamily = _symbolProperty(sl, "font")
    label = _symbolProperty(sl, "label")
    size = _symbolProperty(sl, "size")
	if "offset" in sl:
        offset = sl["offset"]
        offsetx = _processProperty(offset[0])
        offsety = _processProperty(offset[1])
        layout["text-offset"] = [offsetX, offsetY]

            
    if "haloColor" in sl and "haloSize" in sl:        
        paint["text-halo-width"] =  _symbolProperty(sl, "haloSize")   
        paint["text-halo-color"] = _symbolProperty(sl, "haloColor")

    layout["text-field"] = label    
    layout["text-size"] = size
    layout["text-font"] =  [fontFamily]

    paint["text-color"] = color

    '''
    rotation = -1 * float(qgisLayer.customProperty("labeling/angleOffset"))
    layout["text-rotate"] = rotation

    ["text-opacity"] = (255 - int(qgisLayer.layerTransparency())) / 255.0

    if str(qgisLayer.customProperty("labeling/scaleVisibility")).lower() == "true":
        layer["minzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMin")))
        layer["maxzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMax")))
	'''

    return {"type": "symbol", "paint": paint, "layout": layout}

def _lineSymbolizer(sl, graphicStrokeLayer = 0):
    opacity = _symbolProperty(sl, "opacity")
    color =  sl.get("color", None)
    graphicStroke =  sl.get("graphicStroke", None)
    width = _symbolProperty(sl, "width")
    dasharray = _symbolProperty(sl, "dasharray")
    cap = _symbolProperty(sl, "cap")
    join = _symbolProperty(sl, "join")
    offset = _symbolProperty(sl, "offset")

    paint = {}
    if graphicStroke is not None:
    	pass #TODO

   	paint["line-offset"] = offset
    if color is None:
    	paint["visibility"] = "none"
	else:
		paint["line-width"] = width
		paint["line-opacity"] = opacity
		paint["line-color"] = color                
    if dasharray is not None:
        paint["line-dasharray"] = dasharray
    if offset is not None:
        paint["line-offset"] = offset
    
    return {"type": "line", "paint": paint}
    
def _geometryFromSymbolizer(sl):
    geomExpr = convertExpression(sl.get("Geometry", None))
    return geomExpr       

def _iconSymbolizer(sl):
    path = os.splitext(os.basename(sl["image"])[0])
    rotation = _symbolProperty(sl, "rotate")

    paint = {}
    paint["icon-image"] = path
    paint["icon-rotate"] = rotation
    return {"type": "symbol", "paint": paint}

def _markSymbolizer(sl):
    size = _symbolProperty(sl, "size")
    #rotation = _symbolProperty(sl, "rotate")
    #outlineDasharray = _symbolProperty(sl, "strokeDasharray")
    #shape = _symbolProperty(sl, "wellKnownName")
    opacity = _symbolProperty(sl, "opacity")
    color = _symbolProperty(sl, "color")
    outlineColor = _symbolProperty(sl, "strokeColor")
    outlineWidth = _symbolProperty(sl, "strokeWidth")
    
    paint["circle-radius"] = ["/", size, "2.0"]
    mark = Element("Mark")
    _addSubElement(mark, "WellKnownName", shape)
    fill = SubElement(mark, "Fill")
    paint["circle-color"] = color
	paint["circle-opacity"] = opacity
	paint["circle-stroke-width"] = outlineWidth
	paint["circle-stroke-color"] = outlineColor
	
    return {"type": "circle", "paint": paint}

def _fillSymbolizer(sl):
    paint = {}
    opacity = _symbolProperty(sl, "opacity")
    color =  sl.get("color", None)
    graphicFill =  sl.get("graphicFill", None)
    if graphicFill is not None:
    	#TODO
    paint["fill-opacity"] = opacity
    if color is not None:                
        paint["fill-color"] = color

    outlineColor = _symbolProperty(sl, "outlineColor")
    if outlineColor is not None:
		#TODO
		pass

    return {"type": "fill", "paint": paint}