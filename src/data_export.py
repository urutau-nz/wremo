'''
Export data for the d3 app
'''
import yaml
import main
import pandas as pd

config_filename = 'main'
# import config file
with open('./config/{}.yaml'.format(config_filename)) as file:
    config = yaml.load(file)

# connect to the psql database
db = main.init_db(config)

# histogram data



# distance as csv - only nonzero pop
sql = "SELECT geoid, dest_type, distance as lat FROM nearest_block WHERE population > 0"
dist = pd.read_sql(sql, db['con'])
dist.to_csv('data/results/distances.csv')


# topojson




# destinations: dest_type, lat, lon
sql = "SELECT dest_type, st_x(geom) as lon, st_y(geom) as lat FROM destinations"
dist = pd.read_sql(sql, db['con'])
dist.to_csv('data/results/destinations.csv')

