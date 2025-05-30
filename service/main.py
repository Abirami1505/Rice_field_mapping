import ee
from django.http import FileResponse
from django.core.exceptions import BadRequest
from .constants import DATASET,FEATURES,MODEL_LIST
from .data_processing import compute_feature,filter_dataset,false_colour_composite
from .conversion import geojson_to_ee, shp_to_ee, shp_zip_to_ee
from .speckle_filters import boxcar

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
from utils.credentials import EE_CREDENTIAL
import json
import tempfile
import gzip

boundary_file="data/TAMIL NADU_DISTRICTS.shp"

default_download_scale = 250

rice_vis_params = {"min": 0, "max": 1, "opacity": 1, "palette": ["ffffff", "328138"]}

rice_thumbnail_params = {"min": 0, "max": 2, "opacity": 1, "palette": ["000000", "328138", "ffffff"]}

seasons=['sowing','peak','harvest']

def make_composite(data_pool,start_date,end_date,days,method):
    def getComposite(date):
        advanced_date=date.advance(days,'day')
        advanced_millis=advanced_date.millis()
        end_millis_limit=ee.Date(end_date).millis()
        end_millis=ee.Number(advanced_millis).min(end_millis_limit)
        filtered_pool=data_pool.filterDate(date,ee.Date(end_millis))

        if method=='minimum':
            season_data=filtered_pool.min()
        elif method=='maximum':
            season_data=filtered_pool.max()
        elif method=='median':
            season_data=filtered_pool.median()
        elif method=='mean':
            season_data=filtered_pool.mean()
        elif method == 'mode':
            season_data = filtered_pool.mode()
        else:
            raise BadRequest("Unrecognized composite type")
        return ee.Algorithms.If(filtered_pool.size().gt(0), season_data.set('system:time_start', date.millis()))
    
    def map_func(dateMillis):
        date = ee.Date(dateMillis)
        return getComposite(date)
    
    gap_difference = ee.Date(start_date).advance(days, 'day').millis().subtract(ee.Date(start_date).millis())
    list_map = ee.List.sequence(ee.Date(start_date).millis(), ee.Date(end_date).millis(), gap_difference)

    composites = ee.ImageCollection.fromImages(list_map.map(map_func).removeAll([None]))

    return composites

def get_phenology(data):
    start_date=data['phenology_dates']['start_date']
    end_date=datetime.strptime(data['phenology_dates']['end_date'],'%Y-%m')
    end_date+=relativedelta(months=+1)
    end_date=end_date.strftime('%Y-%m')
    
    data_filters=data['dataset']
    print(data_filters.keys())
    samples=data['samples']
    try:
        samples_ee=geojson_to_ee(samples)
        print(type(samples_ee))
    except Exception as e:
        print("Can't read geojson files:",e)
    i=samples_ee.geometry()
    print(data_filters)
    data_pool=filter_dataset(data_filters,samples_ee.geometry())
    data_pool=data_pool.filterDate(start_date,end_date)

    days=int(data_filters['composite_days'])
    method=data_filters['composite']

    composite=make_composite(data_pool,start_date,end_date,days,method)

    feature_pool=compute_feature(data_filters['name'],composite,data_filters['feature'])

    year_img=feature_pool.map(lambda img: img.unmask(99999).rename(ee.Number(img.get('system:time_start')).format('%d').cat('_feature'))).toBands()

    sample_res=year_img.sampleRegions(samples_ee,scale=10,geometries=True)
    print("done")

    return sample_res.getInfo()

def get_monthly_composite(start_date,end_date):
    return false_colour_composite(start_date,end_date)

def compute_hectare_area(img, band_name, boundary, scale)->ee.Number:
    #print("entered:",boundary,scale,"done")
    area=ee.Number(img.multiply(ee.Image.pixelArea()).reduceRegion(ee.Reducer.sum(),boundary,scale,None,None,False,1e13).get(band_name)).divide(1e4).getInfo()
    print(area)
    return area

def run_threshold_based_classification(filters):
    data_filters=filters['dataset']
    if data_filters['boundary']=='upload':
        boundary=shp_zip_to_ee(data_filters['boundary_file'])
    else:
        default_boundary=shp_to_ee(boundary_file)
        boundary=ee.Feature(default_boundary.filterMetadata('DISTRICT','equals',data_filters['boundary']).first())

    crop_mask=None
    if data_filters["use_crop_mask"]:
        if data_filters["crop_mask"]:
            crop_mask=ee.Image(data_filters['crop_mask']).clip(boundary)
        else:
            raise BadRequest("Invalid crop mask argument")
            
    pool=filter_dataset(data_filters,boundary.geometry())

    op=filters['op']
    season_filters=filters['seasons']
    season_res={season['name']: None for season in season_filters}

    def map_composites(composite):
        composite=ee.Image(composite)
        if data_filters["use_crop_mask"]:
            return (composite.lte(thres_max)).And(composite.gte(thres_min)).updateMask(crop_mask).clip(boundary)
        else:
            return (composite.lte(thres_max)).And(composite.gte(thres_min)).clip(boundary)
            
    for season in season_filters:
        start_date, end_date = season['start'], season['end']

        thres_min,thres_max=float(season['min']),float(season['max'])

        season_data_pool=pool.filter(ee.Filter.date(start_date,end_date))

        if data_filters['name'] in DATASET['Radar']:
            season_data_pool=season_data_pool.map(lambda img: boxcar(img))
        season_data_pool=compute_feature(data_filters['name'],season_data_pool,data_filters['feature'])

        composites=make_composite(season_data_pool,start_date,end_date,days=int(data_filters["composite_days"]),method=data_filters['composite'])
        #print("crossed:",composites)
        thresholded_composites = composites.map(map_composites)
        season_res[season['name']]=thresholded_composites.Or()
    season_res_list=list(season_res.values())
    combined_res=season_res_list[0]
    for i in range(1,len(season_res_list)):
        if op=='and':
            combined_res=combined_res.And(season_res_list[i])
        else:
            combined_res=combined_res.Or(season_res_list[i])

    if data_filters['name'] in DATASET['Radar']:
        scale=DATASET['Radar'][data_filters['name']]['scale']
    else:
        scale=DATASET['Optical'][data_filters['name']]['scale']
    return combined_res,boundary,scale

def make_empirical_results(img,boundary,scale):
    res={}
    area=compute_hectare_area(img,'feature',boundary.geometry(),scale)
    thumbnail_img=img.unmask(2)
    res['combined']={
        'title_url':img.getMapId(rice_vis_params)['tile_fetcher'].url_format,
        'download_url':thumbnail_img.getThumbURL({
            **rice_thumbnail_params,
            'dimensions':1920,
            'region':boundary.geometry(),
            'format':'jpg'
        }),
        "area":area
    }

    return res

def export_result(img,boundary,scale):
    task=ee.batch.Export.image.toDrive(img,**{
        "description":str(time.time()),
        "region":boundary.geometry(),
        "scale":scale,
        "maxPixels":1e13
    })
    task.start()
    return task.status()['id']

def get_task_list():
    tasks=ee.batch.Task.list()
    res=[]
    for task in tasks:
        res.append(task.status())
    return res

def get_the_task(id):
    tasks=ee.batch.Task.list()
    for task in tasks:
        if task.status()['id']==id:
            return task.status()
    return None

def download_file(id):
    status=get_the_task(id)
    if status is None:
        return None
    
    gauth=GoogleAuth()
    scopes=['https://ww.googleapis.com/auth/drive']
    gauth.credentials=ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(EE_CREDENTIAL),
        scopes=scopes
    )
    drive=GoogleDrive(gauth)

    file_list=drive.ListFile({'q':"'root in parents and trashed=false"}).GetList()

    for file in file_list:
        filename=file['title']
        if filename == status['description']+".tif":
            file.GetContentFile("results/"+filename,mimetype="image/tiff")

            return "results/"+filename
        return None

CLASS_FIELD = '$class'

def run_supervised_classification(filters,samples):
    dataset_filters = filters['dataset']
    classification_filters=filters['classification']
    start_date, end_date = classification_filters['start_date'], classification_filters['end_date']

    class_property = classification_filters['class_property']
    class_name = class_property['name']
    class_value = class_property['positiveValue']
    for feature in samples["features"]:
        if feature['properties'][class_name]==class_value:
            feature['properties'][CLASS_FIELD]=1
        else:
            feature['properties'][CLASS_FIELD]=0

    samples_ee = geojson_to_ee(samples)

    if dataset_filters['name'] in DATASET['Radar']:
        scale=DATASET['Radar'][dataset_filters['name']]['scale']
    else:
        scale=DATASET['Optical'][dataset_filters['name']]['scale']

    if dataset_filters['boundary']=='upload':
        uploaded_file = dataset_filters['boundary_file']
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        boundary = shp_zip_to_ee(tmp_path)
    else:
        default_boundary=shp_to_ee(default_boundary)
        boundary = ee.Feature(
            default_boundary.filterMetadata(
                'DISTRICT','equals',dataset_filters['boundary']
            ).first()
        )

    pool = filter_dataset(dataset_filters,boundary.geometry()).filterDate(start_date,end_date)

    if dataset_filters['name'] in DATASET['Radar']:
        pool=pool.map(lambda img: boxcar(img))

    pool=compute_feature(dataset_filters['name'],pool,dataset_filters['feature'])

    composites= make_composite(pool,start_date,end_date,days=int(dataset_filters['composite_days']),method=dataset_filters['composite'])

    stacked_image=composites.toBands()

    points = stacked_image.sampleRegions(samples_ee, [CLASS_FIELD], scale=scale).randomColumn().set('band_order',stacked_image.bandNames())

    # Safely cast training ratio
    training_ratio = float(classification_filters['training_ratio'])

    training = points.filter(ee.Filter.lt('random', training_ratio))
    testing = points.filter(ee.Filter.gte('random', training_ratio))

    model_func = MODEL_LIST[classification_filters['model']]

    specs = classification_filters['model_specs']

    # --- Cast string numbers to proper types ---
    for k, v in specs.items():
        if isinstance(v, str):
            # Try convert to int or float
            try:
                if '.' in v:
                    specs[k] = float(v)
                else:
                    specs[k] = int(v)
            except ValueError:
                pass  # Keep original if casting fails
    model_ee = model_func(**specs).train(training, CLASS_FIELD)

    #model_ee = model_func(**classification_filters['model_specs']).train(training, CLASS_FIELD)

    test_pred=testing.classify(model_ee)
    confusion_matrix=test_pred.errorMatrix(CLASS_FIELD,'classification')

    classified=stacked_image.classify(model_ee)

    crop_mask = None

    if dataset_filters["use_crop_mask"]:
        crop_mask=ee.Image(dataset_filters["crop_mask"]).clip(boundary.geometry())
        classified = classified.updateMask(crop_mask)
    classified=classified.clip(boundary.geometry())

    if dataset_filters['name'] in DATASET['Radar']:
        scale=DATASET['Radar'][dataset_filters['name']]['scale']
    else:
        scale=DATASET['Optical'][dataset_filters['name']]['scale']
    return classified,boundary,scale,confusion_matrix

def make_classification_results(img,boundary, scale, confusion_matrix):
    res={}
    area=compute_hectare_area(img,'classification',boundary.geometry(),scale)

    oa = confusion_matrix.accuracy()
    kappa=confusion_matrix.kappa()

    thumbnail_img =img.unmask(2)

    res={
        'classification_result':{
            'tile_url':img.getMapId(rice_vis_params)['tile_fetcher'].url_format,
            'download_url':thumbnail_img.getThumbURL({
                **rice_thumbnail_params,
                'dimensions':1920,
                'region':boundary.geometry(),
                'format':'jpg'
            }),
        },
        'area':area,
        'confusion_matrix':json.dumps(confusion_matrix.getInfo()),
        'oa':oa.getInfo(),
        'kappa':kappa.getInfo(),
    }
    return res


        
