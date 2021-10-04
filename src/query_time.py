'''
Init the database
Query origin-destination pairs using OSRM
'''
############## Imports ##############
# Packages
import math
import os.path
import io
import code
import numpy as np
import pandas as pd
import itertools
from datetime import datetime
import subprocess
# functions - geospatial
import osgeo.ogr
import geopandas as gpd
import shapely
from geoalchemy2 import Geometry, WKTElement
# functions - data management
import psycopg2
from sqlalchemy.types import Float, Integer
from sqlalchemy.engine import create_engine
# functions - parallel
import multiprocessing as mp
from joblib import Parallel, delayed
from tqdm import tqdm
# functions - requests
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
# functions - logging
import logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

############## Main ##############
def main(config):
    '''
    gathers context and runs functions based on 'script_mode'
    '''
    # gather data and context
    db = connect_db(config)
    # query the distances
    time_steps = [0,1,2,3,4,5]
    for time in time_steps:
        print(time)
        origxdest = query_points(db, config, time)
        origxdest.to_sql('parcel_distance', db['engine'], if_exists='append',index=False)
        #write_to_postgres(origxdest, db)
    # close the connection
    db['con'].close()
    logger.info('Database connection closed')


def connect_db(config):
    '''create the database and then connect to it'''
    # SQL connection
    db = config['SQL'].copy()
    db['passw'] = open('pass.txt', 'r').read().strip('\n')
    # connect to database
    db['engine'] = create_engine('postgresql+psycopg2://postgres:' + db['passw'] + '@' + db['host'] + '/' + db['database_name'] + '?port=' + db['port'])
    db['address'] = "host=" + db['host'] + " dbname=" + db['database_name'] + " user=postgres password='"+ db['passw'] + "' port=" + db['port']
    db['con'] = psycopg2.connect(db['address'])
    logger.info('Database connection established')
    return(db)


############## Query Points ##############
def query_points(db, config, time):
    '''
    query OSRM for distances between origins and destinations
    '''
    logger.info('Querying invoked for {} in {}'.format(config['transport_mode'], config['location']['state']))
    location = config['location']
    # connect to db
    cursor = db['con'].cursor()

    # get list of all origin ids
    sql = "SELECT * FROM origin"
    orig_df = gpd.GeoDataFrame.from_postgis(sql, db['con'], geom_col='geom')

    orig_df['x'] = orig_df.geom.x
    orig_df['y'] = orig_df.geom.y
    # drop duplicates
    orig_df.drop('geom',axis=1,inplace=True)
    orig_df.drop_duplicates(inplace=True)
    # set index (different format for different census blocks)
    orig_df.sort_values(by=[config['orig_id']], inplace=True)
    orig_df = orig_df.set_index(config['orig_id'])
    # get list of destination ids
    sql = "SELECT * FROM destinations"
    dest_df = gpd.GeoDataFrame.from_postgis(sql, db['con'], geom_col='geom')
    dest_df = dest_df.set_index('dest_type')
    dest_df = dest_df.loc[config['services']]
    dest_df = dest_df.reset_index()

    dest_df = dest_df.set_index('id_dest')
    dest_df['lon'] = dest_df.geom.x
    dest_df['lat'] = dest_df.geom.y
    dest_df = dest_df[dest_df[str(time)] != 3] # 3 is the value given for closed
    # list of origxdest pairs
    origxdest = pd.DataFrame(list(itertools.product(orig_df.index, dest_df.index)), columns = ['id_orig', 'id_dest'])
    for metric in config['metric']:
        origxdest['{}'.format(metric)] = None
    origxdest['dest_type'] = len(orig_df)*list(dest_df['dest_type'])
    # df of durations, distances, ids, and co-ordinates
    origxdest = execute_table_query(origxdest, orig_df, dest_df, config)
    origxdest['time'] = time
    return origxdest

############## Parallel Table Query ##############
def execute_table_query(origxdest, orig_df, dest_df, config):
    # Use the table service so as to reduce the amount of requests sent
    # https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md#table-service

    batch_limit = 10000
    dest_n = len(dest_df)
    orig_n = len(orig_df)
    orig_per_batch = int(batch_limit/dest_n)
    batch_n = math.ceil(orig_n/orig_per_batch)

    #create query string
    osrm_url = config['OSRM']['host'] + ':' + config['OSRM']['port']
    base_string = osrm_url + "/table/v1/{}/".format(config['transport_mode'])

    # make a string of all the destination coordinates
    dest_string = ""
    dest_df.reset_index(inplace=True, drop=True)
    for j in range(dest_n):
        #now add each dest in the string
        dest_string += str(dest_df['lon'][j]) + "," + str(dest_df['lat'][j]) + ";"
    #remove last semi colon
    dest_string = dest_string[:-1]

    # options string ('?annotations=duration,distance' will give distance and duration)
    if len(config['metric']) == 2:
        options_string_base = '?annotations=duration,distance'
    else:
        options_string_base = '?annotations={}'.format(config['metric'][0]) #'?annotations=duration,distance'
    # loop through the sets of
    orig_sets = [(i, min(i+orig_per_batch, orig_n)) for i in range(0,orig_n,orig_per_batch)]

    # create a list of queries
    query_list = []
    for i in orig_sets:
        # make a string of all the origin coordinates
        orig_string = ""
        orig_ids = range(i[0],i[1])
        for j in orig_ids:
            #now add each dest in the string
            orig_string += str(orig_df.x.iloc[j]) + "," + str(orig_df.y.iloc[j]) + ";"
        # make a string of the number of the sources
        source_str = '&sources=' + str(list(range(len(orig_ids))))[1:-1].replace(' ','').replace(',',';')
        # make the string for the destinations
        dest_idx_str = '&destinations=' + str(list(range(len(orig_ids), len(orig_ids)+len(dest_df))))[1:-1].replace(' ','').replace(',',';')
        # combine and create the query string
        options_string = options_string_base + source_str + dest_idx_str
        query_string = base_string + orig_string + dest_string + options_string
        # append to list of queries
        query_list.append(query_string)
    # # Table Query OSRM in parallel
    #define cpu usage
    num_workers = np.int(mp.cpu_count() * config['par_frac'])
    #gets list of tuples which contain 1list of distances and 1list
    logger.info('Querying the origin-destination pairs:')
    results = Parallel(n_jobs=num_workers)(delayed(req)(query_string, config) for query_string in tqdm(query_list))
    logger.info('Querying complete.')
    # get the results in the right format
    if len(config['metric']) == 2:
        dists = [l for orig in results for l in orig[0]]
        durs = [l for orig in results for l in orig[1]]
        origxdest['distance'] = dists
        origxdest['duration'] = durs
    else:
        formed_results = [result for query in results for result in query]
        origxdest['{}'.format(config['metric'][0])] = formed_results
    return(origxdest)

############## Read JSON ##############
def req(query_string, config):
    response = requests.get(query_string).json()
    if len(config['metric']) == 2:
        temp_dist = [item for sublist in response['distances'] for item in sublist]
        temp_dur = [item for sublist in response['durations'] for item in sublist]
        return temp_dist, temp_dur
    else:
        return [item for sublist in response['{}s'.format(config['metric'][0])] for item in sublist]


############## Save to SQL ##############
def write_to_postgres(df, db, indices=True):
    ''' quickly write to a postgres database
        from https://stackoverflow.com/a/47984180/5890574'''
    table_name = db['table_name']
    logger.info('Writing data to SQL')
    df.head(0).to_sql(table_name, db['engine'], if_exists='append',index=False) #truncates the table
    conn = db['engine'].raw_connection()
    cur = conn.cursor()
    output = io.StringIO()
    df.to_csv(output, sep='\t', header=False, index=False)
    output.seek(0)
    cur.copy_from(output, table_name, null="") # null values become ''
    logger.info('Distances written successfully to SQL as "{}"'.format(table_name))
    # update indices
    logger.info('Updating indices on SQL')
    if indices == True:
        if table_name == db['table_name']:
            queries = [
                        'CREATE INDEX "{0}_dest_id" ON {0} ("id_dest");'.format(db['table_name']),
                        'CREATE INDEX "{0}_orig_id" ON {0} ("id_orig");'.format(db['table_name'])
                        ]
        for q in queries:
            cur.execute(q)
    conn.commit()


if __name__ == '__main__':
    main()
