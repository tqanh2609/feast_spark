from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark import StorageLevel
from pyspark.sql.functions import col

import subprocess
import sys

from datetime import datetime

import pandas as pd

# Define the list of packages to install
packages = [
    "feast",
    "feast[spark]",
    "feast[singlestore]",
    "pyarrow==19.0.1"
]

# Construct the pip install command
command = [sys.executable, "-m", "pip", "install"] + packages

# Execute the command
subprocess.check_call(command)

# client
wxd_hms_username = 'devadmin'
wxd_hms_password = 'AX2Z1MBUoOergIb'

# landingdev
iceberg_catalog = "thidiemcatalog"
access_key = "WEeGX66cjJBVgira3DcU"
secret_key = "BgbbrH08yKFcM4rz1RPUlRxWn3yuMV46W1nE0uTO"
bucket_name = "thidiem"
hivemetastore_host = "thrift://ibm-lh-lakehouse-hive-metastore-svc.zen.svc.cluster.local:9083"

s3_endpoint = "https://rook-ceph-rgw.vnpt.vn"

spark = SparkSession.builder \
            .appName("qa_feast_spark") \
            .config("spark.datasource.singlestore.clientEndpoint", "192.168.0.121:32216") \
            .config("spark.datasource.singlestore.user", "admin") \
            .config("spark.datasource.singlestore.password", "secretpass") \
            .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
            .config("spark.hive.metastore.use.SSL", "true") \
            .config("spark.hive.metastore.truststore.type", "JKS") \
            .config("spark.hive.metastore.truststore.path", "file:///opt/ibm/jdk/lib/security/cacerts") \
            .config("spark.hive.metastore.truststore.password", "changeit") \
            .config("spark.hive.metastore.client.auth.mode", "PLAIN") \
            .config("spark.hive.metastore.client.plain.username", wxd_hms_username) \
            .config("spark.hive.metastore.client.plain.password", wxd_hms_password) \
            .config(f"spark.sql.catalog.{iceberg_catalog}", "org.apache.iceberg.spark.SparkCatalog") \
            .config(f"spark.sql.catalog.{iceberg_catalog}.type", "hive") \
            .config(f"spark.sql.catalog.{iceberg_catalog}.uri", hivemetastore_host) \
            .config(f"spark.hadoop.fs.s3a.bucket.{bucket_name}.endpoint", s3_endpoint) \
            .config(f"spark.hadoop.fs.s3a.bucket.{bucket_name}.access.key", access_key) \
            .config(f"spark.hadoop.fs.s3a.bucket.{bucket_name}.secret.key", secret_key) \
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "true") \
            .config("spark.hadoop.fs.s3a.path.style.access", "true") \
            .config("spark.hadoop.fs.s3a.access.key", access_key) \
            .config("spark.hadoop.fs.s3a.secret.key", secret_key) \
            .config("spark.hadoop.fs.s3a.endpoint", s3_endpoint) \
            .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider") \
            .config("spark.executor.extraJavaOptions", "-Daws.java.v1.disableDeprecationAnnouncement=true") \
            .config("spark.driver.extraJavaOptions", "-Daws.java.v1.disableDeprecationAnnouncement=true") \
            .getOrCreate()

import os

from feast import FeatureStore
from feast.data_source import PushMode

# Specify the path you want to change to
path = '/spark_job/QuangAnh/feastspark/main/'

# Change the current working directory
os.chdir(path)

# Optional: Verify the change
print("Current working directory:", os.getcwd())

def fetch_historical_features_entity_df(store: FeatureStore, for_batch_scoring: bool):
    # Note: see https://docs.feast.dev/getting-started/concepts/feature-retrieval for more details on how to retrieve
    # for all entities in the offline store instead
    entity_df = pd.DataFrame.from_dict(
        {
            # entity's join key -> entity values
            "driver_id": [1001, 1002, 1003],
            # "event_timestamp" (reserved key) -> timestamps
            "event_timestamp": [
                datetime(2021, 4, 12, 10, 59, 42),
                datetime(2021, 4, 12, 8, 12, 10),
                datetime(2021, 4, 12, 16, 40, 26),
            ],
            # (optional) label name -> label values. Feast does not process these
            "label_driver_reported_satisfaction": [1, 5, 3],
            # values we're using for an on-demand transformation
            "val_to_add": [1, 2, 3],
            "val_to_add_2": [10, 20, 30],
        }
    )
    # For batch scoring, we want the latest timestamps
    if for_batch_scoring:
        entity_df["event_timestamp"] = pd.to_datetime("now", utc=True)

    training_df = store.get_historical_features(
        entity_df=entity_df,
        features=[
            "driver_hourly_stats:conv_rate",
            "driver_hourly_stats:acc_rate",
            "driver_hourly_stats:avg_daily_trips",
            # "transformed_conv_rate:conv_rate_plus_val1",
            # "transformed_conv_rate:conv_rate_plus_val2",
        ],
    ).to_df()
    print(training_df.head())


def fetch_online_features(store, use_feature_service: bool):
    entity_rows = [
        # {join_key: entity_value}
        {
            "driver_id": 1001,
            "val_to_add": 1000,
            "val_to_add_2": 2000,
        },
        {
            "driver_id": 1002,
            "val_to_add": 1001,
            "val_to_add_2": 2002,
        },
    ]
    if use_feature_service:
        features_to_fetch = store.get_feature_service("driver_activity_v1")
    else:
        features_to_fetch = [
            "driver_hourly_stats:acc_rate",
            "driver_hourly_stats:avg_daily_trips",
            # "transformed_conv_rate:conv_rate_plus_val1",
            # "transformed_conv_rate:conv_rate_plus_val2",
        ]
    returned_features = store.get_online_features(
        features=features_to_fetch,
        entity_rows=entity_rows,
    ).to_dict()
    for key, value in sorted(returned_features.items()):
        print(key, " : ", value)

store = FeatureStore(repo_path=".")
print("\n--- Run feast apply ---")
subprocess.run(["feast", "apply"])

print("\n--- Historical features for training ---")
fetch_historical_features_entity_df(store, for_batch_scoring=False)

print("\n--- Historical features for batch scoring ---")
fetch_historical_features_entity_df(store, for_batch_scoring=True)

print("\n--- Load features into online store ---")
store.materialize_incremental(end_date=datetime.now())

print("\n--- Online features ---")
fetch_online_features(store)
