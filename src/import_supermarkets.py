'''
08/06/2021
Mitchell Anderson

Takes csv of coordinates, creates points, and appends to destination table in SQL
'''

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
from shapely.geometry import Point
from geoalchemy2 import Geometry, WKTElement
import shapely.geometry
import numpy as np
import requests
import json
import main
import yaml
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# config
with open('./config/main.yaml') as file:
    config = yaml.load(file)
crs = config['set_up']['projection']
# init SQL connection
db = main.init_db(config)
engine = db['engine']


df = pd.read_csv(r'data/raw/wremo_supermarkets.csv')

lats = df['Y'].tolist()
lons = df['X'].tolist()

df_dest = gpd.GeoDataFrame()
geometry = [Point(xy) for xy in zip(lons, lats)]
gdf_dests = gpd.GeoDataFrame(df_dest, crs=crs, geometry=geometry)
gdf_dests['dest_type'] = 'supermarket'
gdf_dests['id_dest'] = np.arange(478, 478+len(gdf_dests))
gdf_dests['id_type'] = None
gdf_dests['index'] = np.arange(479, 479+len(gdf_dests))
print(gdf_dests)

gdf_dests.to_postgis('destinations', engine, if_exists='append', dtype={'geometry': Geometry('POINT', srid=crs)})