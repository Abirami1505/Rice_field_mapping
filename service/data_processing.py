import ee
from django.core.exceptions import BadRequest
from .constants import DATASET,FEATURES
import datetime
from dateutil.relativedelta import relativedelta

def dBtoPower(img):
    return ee.Image(10).pow(img.divide(10))

def filter_dataset(data_filters,boundry=None):
    '''
    structure of data_filters:
        {
            "start_date": "YYYY-MM-DD",  # Start date for filtering (string)
            "end_date": "YYYY-MM-DD",    # End date for filtering (string)
            "name": "Dataset_Name",      # Name of the dataset (string, must be in DATASET_LIST['radar'] or DATASET_LIST['optical'])
            
            # Radar-specific keys (for Sentinel-1)
            "feature": "VV" or "VH" or "VH/VV",  # Type of radar polarization (string)
            "ascd": True or False,  # Include ascending orbit (boolean)
            "desc": True or False,  # Include descending orbit (boolean)

            # Optical-specific key (for Sentinel-2 or Landsat)
            "cloud": 0-100  # Maximum allowed cloud cover percentage (integer)
        }
    '''

    filters=[]
    if data_filters['start_date'] and data_filters['end_date']:
        filters.append(ee.Filter.date(data_filters['start_date'],data_filters['end_date']))

    dataset_name=data_filters['name']
    if dataset_name not in DATASET['Radar'] and dataset_name not in DATASET['Optical']:
        raise BadRequest("Dataset name invalid")
    
    if dataset_name in DATASET['Radar']:
        feature= data_filters['feature']
        if feature not in FEATURES['radar']:
            raise BadRequest("Feature invalid")
        
        filters.append(ee.Filter.eq('instrumentMode','IW'))

        if feature=="VV":
            filters.append(ee.Filter.listContains('transmitterReceiverPolarisation','VV'))

        elif feature=="VH":
            filters.append(ee.Filter.listContains('transmitterReceiverPolarisation','VH'))

        elif feature=="VH/VV":
            filters.append(ee.Filter.listContains('transmitterReceiverPolarisation','VH'))
            filters.append(ee.Filter.listContains('transmitterReceiverPolarisation','VV'))

        if not data_filters['ascd']:
            filters.append(ee.Filter.neq('orbitProperties_pass','ASCENDING'))
        elif not data_filters['desc']:
            filters.append(ee.Filter.neq('orbitProperties_pass','DESCENDING'))

    else:
        cloud_fieldName = None

        if data_filters['name'].startswith("COPERNICUS/S2"):
            cloud_fieldName="CLOUDY_PIXEL_PERCENTAGE"
        elif data_filters['name'].startswith("LANDSAT"):
            cloud_fieldName="CLOUD_COVER"

        if cloud_fieldName is not None:
            cloud=int(data_filters['cloud'])
            filters.append(ee.Filter.lte(cloud_fieldName,cloud))

    pool=ee.ImageCollection(dataset_name).filter(ee.Filter(filters))
    if boundry:
        pool = pool.filterBounds(boundry)

    return pool

def compute_feature(dataset_name,pool,feature):
    def map_radar(img):
        #for radar dataset
        nonlocal feature
        backscatter_img=dBtoPower(img)
        exp="b('VH') / b('VV')"
        feature_img=backscatter_img.expression(exp,{'vh':img.select('VH'),'vv':img.select('VV')})
        return feature_img.rename('feature').copyProperties(img).set('system:time_start', img.get('system:time_start'))

    def map_optical(img):
        #for optical dataset
        nonlocal feature
        bands=DATASET['Optical'][dataset_name]['bands']
        nir=bands['NIR']
        red=bands['red']
        green=bands['green']
        if feature=='NDVI':
            feature_img=img.normalizedDifference([nir,red]).rename('feature')
        elif feature=='EVI':
            blue=bands['blue']
            exp="2.5 * ((b('nir')-b('red')) / (b('nir') + 6 * b('red') - 7.5 * b('blue') + 1))"
            feature_img=img.expression(exp,{'nir':img.select(nir),'red':img.select(red),'blue':img.select(blue)}).rename('feature')
        elif feature=='NDMWI':
            feature_img=img.normalizedDifference([green,nir]).rename('feature')
        elif feature=='MNDWI':
            swir1=bands['SWIR1']
            feature_img=img.normalizedDifference([green,swir1]).rename('feature')
        else:
            feature_img=None
        return feature_img.copyProperties(img).set('system:time_start', img.get('system:time_start'))
    
    if feature in FEATURES['radar']:
        if feature in ['VV','VH']:
            return pool.select(feature).map(lambda img: img.rename('feature').copyProperties(img).set('system:time_start',img.get('system:time_start')))
        else:
            return pool.map(map_radar)
    elif feature in FEATURES['optical']:
        return pool.map(map_optical)

def false_colour_composite(start_date,end_date):
    start_date=datetime.datetime.strptime(start_date,"%Y-%m")
    end_date=datetime.datetime.strptime(end_date,"%Y-%m")

    months=[]
    current=start_date
    while current<=end_date:
        months.append(current.strftime("%Y-%m"))
        current+=relativedelta(months=1)

    if start_date.year>2015 or (start_date.year==2015 and start_date.month>6):
        dataset=ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        scale=0.0001
        offset=0
        vis_params={"bands":["B8","B4","B3"],"min":0,"max":0.5}
    elif start_date.year>1984 or (start_date.year==1984 and start_date.month>=3):
        dataset=ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
        scale=0.0000275
        offset=-0.2
        vis_params={"bands":["SR_B4","SR_B3","SR_B2"],"min":0,"max":0.5}
    elif start_date.year>2013 or (start_date.year==2013 and start_date.month>=3):
        dataset=ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        scale=0.0000275
        offset=-0.2
        vis_params={"bands":["SR_B5","SR_B4","SR_B3"],"min":0,"max":0.5}

    urls={}
    for month in months:
        m=datetime.datetime.strptime(month,"%Y-%m")
        end_month=m+relativedelta(months=1)
        data_filtered=dataset.filterDate(month,end_month)
        composite=data_filtered.median().multiply(scale).add(offset)
        urls[month] = composite.getMapId(vis_params)['tile_fetcher'].url_format
    return urls