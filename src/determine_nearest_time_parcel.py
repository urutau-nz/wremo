'''
Create a table with the nearest distance, grouped by destination type for each of the blocks
'''
import main
import yaml 
import psycopg2
from sqlalchemy.types import Float, Integer
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
import pandas as pd
# functions - logging
import logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

def main(db):

    conn = db['engine'].raw_connection()
    cur = conn.cursor()

    times = [0,1,2,3,4,5]

    dest_types = pd.read_sql('Select distinct(dest_type) from destinations', db['engine'])['dest_type'].values

    # get the nearest distance for each block by each destination type
    queries_1 = ['DROP TABLE IF EXISTS nearest_parcel;',
        'CREATE TABLE IF NOT EXISTS nearest_parcel(geoid TEXT, dest_type TEXT, distance INT, duration INT, time INT)'
    ]
    queries_2 = [''' INSERT INTO nearest_parcel (geoid, dest_type, distance, duration, time)
            SELECT dist.id_orig as geoid, destinations.dest_type, MIN(dist.distance) as distance, MIN(dist.duration) as duration, dist.time as time
            FROM parcel_distance as dist
            INNER JOIN destinations ON dist.id_dest = destinations.id_dest
            INNER JOIN origin ON  dist.id_orig = origin."building_i"
            WHERE destinations.dest_type='{}' AND dist.time='{}'
            GROUP BY dist.id_orig, destinations.dest_type, dist.time;
        '''.format(dest_type, time)
        for dest_type in dest_types
        for time in times]
    queries_3 = ['CREATE INDEX nearest_geoid_parcel ON nearest_parcel (geoid)']

    queries = queries_1 + queries_2 + queries_3

    # import code
    # code.interact(local=locals())
    logger.error('Creating table')
    for q in queries:
        cur.execute(q)
    conn.commit()
    logger.error('Table created')

    db['con'].close()
    logger.error('Database connection closed')
