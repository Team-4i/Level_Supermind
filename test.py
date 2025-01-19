from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import json
import uuid

def check_astra_data():
    # Load credentials
    with open("lsm-token.json") as f:
        secrets = json.load(f)

    # Connect to Astra
    cloud_config = {
        'secure_connect_bundle': 'secure-connect-lsm.zip'
    }
    auth_provider = PlainTextAuthProvider(secrets["clientId"], secrets["secret"])
    cluster = Cluster(cloud=cloud_config, auth_provider=auth_provider)
    session = cluster.connect()
    
    # Set keyspace
    session.set_keyspace('django_keyspace')
    
    # Query UserProfile data
    rows = session.execute("SELECT * FROM user_profile_astra")
    print("\nUser Profiles in Astra DB:")
    for row in rows:
        print(f"Username: {row.username}, Bio: {row.bio}")
    
    # Query ART data
    rows = session.execute("SELECT * FROM art_astra")
    print("\nART Requests in Astra DB:")
    for row in rows:
        print(f"Product: {row.product_name}, Status: {row.status}")

if __name__ == "__main__":
    check_astra_data()