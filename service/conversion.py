import json
import os
import geopandas as gpd
import zipfile
import ee
from django.core.exceptions import BadRequest

def shp_to_geojson(inShp,outJson=None):
    try:
        inShp=os.path.abspath(inShp)
        if outJson==None:
            outJson=os.path.splitext(inShp)[0]+".geoJson"
        
        gdf=gpd.read_file(inShp)

        gdf.to_file(outJson,driver="GeoJSON")

        with open(outJson) as f:
            geojson_data=json.load(f)

        return geojson_data
    
    except Exception as e:
        print("Error in conversion from shape to geojson:",str(e))
        return None

def shp_reader_to_geojson(shp_reader):
    fields = shp_reader.fields[1:]
    field_names = [field[0] for field in fields]
    buffer = []
    for sr in shp_reader.shapeRecords():
        atr = dict(zip(field_names, sr.record))
        geom = sr.shape.__geo_interface__
        buffer.append(dict(type="Feature", geometry=geom, properties=atr))
    
    import json
    geojson = json.dumps({"type": "FeatureCollection",
                            "features": buffer}, indent=2)
    return geojson

def shp_zip_to_ee(file):
    from zipfile import ZipFile
    import re
    from shapefile import Reader
    
    zip = ZipFile(file)
    file_names = zip.namelist()
    shp_filename = None
    shx_filename = None
    dbf_filename = None
    for file_name in file_names:
        shp_match = re.match(r".+\.shp$", file_name)
        shx_match = re.match(r".+\.shx$", file_name)
        dbf_match = re.match(r".+\.dbf$", file_name)
        
        if shp_match:
            shp_filename = file_name
        elif shx_match:
            shx_filename = file_name
        elif dbf_match:
            dbf_filename = file_name
    
    if not shp_filename or not shx_filename or not dbf_filename:
        raise BadRequest("Invalid boundary file")
    
    reader = Reader(shp=zip.open(shp_filename), shx=zip.open(shx_filename), dbf=zip.open(dbf_filename))
    
    geojson_str = shp_reader_to_geojson(reader)
    
    ee_obj = geojson_to_ee(json.loads(geojson_str))
    
    return ee_obj
    
def geojson_to_ee(geo_json):
    if not isinstance(geo_json, dict) and os.path.isfile(geo_json):
        with open(os.path.abspath(geo_json)) as f:
            geo_json = json.load(f)
    
    if geo_json['type'] == 'FeatureCollection':
        features = ee.FeatureCollection(geo_json)
        return features
    elif geo_json['type'] == 'Feature':
        geom = None
        keys = geo_json['properties']['style'].keys()
        if 'radius' in keys:  # Checks whether it is a circle
            geom = ee.Geometry(geo_json['geometry'])
            radius = geo_json['properties']['style']['radius']
            geom = geom.buffer(radius)
        elif geo_json['geometry']['type'] == 'Point':  # Checks whether it is a point
            coordinates = geo_json['geometry']['coordinates']
            longitude = coordinates[0]
            latitude = coordinates[1]
            geom = ee.Geometry.Point(longitude, latitude)
        else:
            geom = ee.Geometry(geo_json['geometry'], "")
        return ee.Feature(geom)
    else:
        raise Exception("Could not convert the geojson to ee.Geometry() - type")

def shp_to_ee(shpFile):
    try:
        json=shp_to_geojson(shpFile)
        ee_object=geojson_to_ee(json)
        return ee_object
    except Exception as e:
        print("Couldn't convert shapefile to ee",e)