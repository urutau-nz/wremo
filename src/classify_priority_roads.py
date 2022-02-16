'''
Mitchell Anderson
25/06/2021

Takes shapefiles of region priority roads, adds new priority column, merges gdfs, saves
'''


import pandas as pd
import geopandas as gpd
import numpy as np

files = ['wlg_city', 'upper_hutt', 'lower_hutt', 'porirua', 'para']

column_names = ['wccReopStg', 'Critical', 'Priority', 'Priority', 'Priority_R']

sub_names = [[['11', 5], ['4', 4], ['3', 3], ['2', 2], ['1', 1], ['0', 5]],
            [['PRI 4', 4], ['PRI 3', 3], ['PRI 2 ALT', 2], ['PRI 2', 2], ['PRI 1a', 1], ['PRI 1', 1]],
            [['Stage 4 - Access to other residential communities', 4], ['Stage 3 - Access to vulnerable communities and food supply - Rest homes, supermarkets', 3], 
            ['Stage 2 - Access to key infrastructure, isolated communities', 2], ['Stage 1a - Potential alternative spine of access, if easily recovered', 1], 
            ['Stage 1 - Spine from quarries to key locations - Hospital, Seaview Marina, Fuel Supply, Marine House, Upper Hutt', 1], ['Choice of routes - to be assessed on the day', 5]],
            [['Priority 4', 4], ['Priority 3', 3], ['Priority 2', 2], ['Priority 1', 1]],
            [['3', 3], ['2', 2], ['1', 1], ['1A', 1]]]

for i in np.arange(0,5):
    gdf = gpd.read_file(r'data/raw/priority_roads_{}.shp'.format(files[i]))
    gdf[column_names[i]] = gdf[column_names[i]].astype(str)
    for j in np.arange(0, len(sub_names[i])):
        gdf[column_names[i]] = gdf[column_names[i]].replace(sub_names[i][j][0], sub_names[i][j][1])
    gdf['priority'] = gdf[column_names[i]]
    gdf = gdf[['priority', 'geometry']]
    if i == 0:
        gdf_merged = gdf[['priority', 'geometry']]
    else:
        gdf_merged = gdf_merged.append(gdf)

gdf_merged = gdf_merged.set_crs(2193)
gdf_merged = gdf_merged.to_crs(4326)

gdf_merged['road_id'] = list(np.arange(1,len(gdf_merged)+1))

gdf_merged.to_file(r'data/raw/merged_priority_roads.shp')

gdf_data = gdf_merged.drop(columns=['geometry'])
gdf_data.to_csv(r'data/raw/merged_priority_roads_data.csv')
