import ee

DATASET={
    "Radar":{
        "COPERNICUS/S1_GRD":{
            "name":"Sentinel-1 SAR GRD: C-band Synthetic Aperture Radar Ground Range Detected, log scaling",
            "scale":10
        }
    },
    "Optical":{
        "MODIS/061/MOD13Q1":{
            "name":"MOD13Q1.061 Terra Vegetation Indices 16-Day Global 250m",
            "scale":250
        },
        "LANDSAT/LT05/C02/T1_TOA":{
            "name":"USGS Landsat 5 TM Collection 2 Tier 1 TOA Reflectance",
            "scale":30,
            "bands":{
                "blue":"B1",
                "green":"B2",
                "red":"B3",
                "NIR":"B4",
                "SWIR1":"B5",
                "SWIR2":"B7"
            }
        },
        "LANDSAT/LC08/C02/T1_TOA":{
            "name":"USGS Landsat 8 Collection 2 Tier 1 TOA Reflectance",
            "scale":30,
            "bands":{
                "blue":"B2",
                "green":"B3",
                "red":"B4",
                "NIR":"B5",
                "SWIR1":"B6"
            }
        },
        "COPERNICUS/S2_HARMONIZED":{
            "name":"Harmonized Sentinel-2 MSI: MultiSpectral Instrument, Level-1C",
            "scale":10,
            "bands":{
                "blue":"B2",
                "green":"B3",
                "red":"B4",
                "NIR":"B8",
                "SWIR1":"B11",
                "SWIR2":"B12"
            }
        }
    }
}

FEATURES={
    "radar":{
        "VV":"VV band",
        "VH":"VH band",
        "VH/VV":"VH/VV cross-ratio"
    },
    "optical":{
        "NDVI":"NDVI",
        "EVI":"EVI",
        "NDWI":"NDWI",
        "MNDWI":"MNDWI"
    }
}

MODEL_LIST={
    'Random Forest': ee.Classifier.smileRandomForest,
    'Gradient Tree Boost': ee.Classifier.smileGradientTreeBoost,
    'Support Vector Machine': ee.Classifier.libsvm,
    'CART': ee.Classifier.smileCart,
    'Naive Bayes': ee.Classifier.smileNaiveBayes,
}