'''
Export data for the d3 app
'''
import yaml
import main
import pandas as pd
import numpy as np
import json
import geopandas as gpd
import topojson as tp

config_filename = 'main'
# import config file
with open('./config/{}.yaml'.format(config_filename)) as file:
    config = yaml.load(file)

# connect to the psql database
db = main.init_db(config)

###
# distance as csv - only nonzero pop
###
sql = "SELECT geoid, dest_type, distance FROM nearest_block WHERE population > 0"
dist = pd.read_sql(sql, db['con'])
dist.to_csv('./data/results/distances.csv')

###
# topojson
###
sql = 'SELECT geoid as id, geometry FROM nearest_block'
blocks = gpd.read_postgis(sql, con=db['con'], geom_col='geometry')
blocks_topo = tp.Topology(blocks).topoquantize(1000) #.to_alt().properties(title='WITH Topoquantization')
blocks_topo.to_json('./data/results/blocks.topojson')

###
# destinations: dest_type, lat, lon
###
sql = "SELECT dest_type, st_x(geom) as lon, st_y(geom) as lat FROM destinations"
dist = pd.read_sql(sql, db['con'])
dist.to_csv('./data/results/destinations.csv')

###
# histogram and cdf
###
# import data
sql = "SELECT geoid, dest_type, distance, population FROM nearest_block WHERE population > 0"
df = pd.read_sql(sql, db['con'])
# set bins
bins = 100#list(range(0,21))
# create hist and cdf
hists = []
for service in df.dest_type.unique():
    df_sub = df[df.dest_type==service]
    # create the hist
    density, division = np.histogram(df_sub.distance/1000, bins = bins, weights=df_sub.population, density=True)
    unity_density = density / density.sum()
    unity_density = np.append(0, unity_density)
    division = np.append(0, division)
    df_new = pd.DataFrame({'pop_perc':unity_density, 'distance':division[:-1]})
    df_new['service']=service
    df_new['pop_perc'] = df_new['pop_perc']*100
    df_new['pop_perc_cum'] = df_new.pop_perc.cumsum()
    hists.append(df_new)
# concat
df_hists = pd.concat(hists)
# export
df_hists.to_csv('./data/results/access_histogram.csv')
