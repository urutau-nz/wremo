'''
Export data for the d3 app
'''
import yaml
import main
import pandas as pd
import numpy as np

config_filename = 'main'
# import config file
with open('./config/{}.yaml'.format(config_filename)) as file:
    config = yaml.load(file)

# connect to the psql database
db = main.init_db(config)

# histogram data



# distance as csv - only nonzero pop
sql = "SELECT geoid, dest_type, distance FROM nearest_block WHERE population > 0"
dist = pd.read_sql(sql, db['con'])
dist.to_csv('./data/results/distances.csv')


# topojson




# destinations: dest_type, lat, lon
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
bins = list(range(0,21))
# create hist and cdf
hists = []
for service in df.dest_type.unique():
    df_sub = df[df.dest_type==service]
    # create the hist
    count, division = np.histogram(df_sub.distance/1000, bins = bins, weights=df_sub.population, density=True)
    count = np.append(0, count)
    division = np.append(0, division)
    df_new = pd.DataFrame({'pop_perc':count, 'distance':division[:-1]})
    df_new['service']=service
    df_new['pop_perc'] = df_new['pop_perc']*100
    df_new['pop_perc_cum'] = df_new.pop_perc.cumsum()
    hists.append(df_new)
# concat
df_hists = pd.concat(hists)
# export
df_hists.to_csv('./data/results/access_histogram.csv')
