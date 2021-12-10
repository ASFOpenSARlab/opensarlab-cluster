"""
Get an estimate of notebook usage by notebook name, user, and time.

It is difficult to estimate which notebooks within an deployment are used the most. How do you define usage? If an user opens an notebook multiple times a day does each time count?

Here we get the daily earilest-used notebook per user. The idea is that users usually do work for a few hours a day. Grabbing the earilest time the notebook opened is a proxy for use all day long.

The results are put into a csv file for better analysis in a spreadsheet. CloudWatch Insights is limited in abilities.

-----

> python3 insights_num_notebooks.py

Output: user_notebooks.csv

"""


import boto3
from datetime import datetime, timedelta
import time
import csv

# Number of days back to start queries
# The script loops from today to QUERY_TO_DAYS_AGO by 1 day each.
QUERY_TO_DAYS_AGO = 90

# The AWS profile name with access to CloudWatch Insights
PROFILE_NAME = 'osl-e'

# The log group being parsed.
# The format of the log is assumed to be from something like...
LOG_GROUP = "/aws/containerinsights/osl-daac-cluster/application"

QUERY = """
    filter @message like '.ipynb'
    | parse '* 200 GET /user/*/api/contents/notebooks/*.ipynb' as pre, user, path
    | fields concat(user, ': ', path, '.ipynb') as pth
    | filter ispresent(user) and ispresent(path)
    | stats min(datefloor(@timestamp, 1d)) as day by pth
    | limit 10000
"""

session = boto3.Session(profile_name=PROFILE_NAME)
logs = session.client('logs')

with open("user_notebooks.csv", 'w') as f:

    fieldnames = ['user', 'notebook', 'timestamp']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()

    for num_day_before in range(1,QUERY_TO_DAYS_AGO+1,1):

        start_date = datetime.today() - timedelta(days=num_day_before)
        end_date = datetime.now() - timedelta(days=num_day_before-1)

        print(f"Query from '{start_date}' to '{end_date}'")

        start_query_response = logs.start_query(
            logGroupName=LOG_GROUP,
            startTime=int(start_date.timestamp()),
            endTime=int(end_date.timestamp()),
            queryString=QUERY,
            limit=10000
        )

        query_id = start_query_response['queryId']

        response = None

        while response == None or response['status'] == 'Running':
            print('Waiting for query to complete ...')
            time.sleep(5)  # Expect 2-3 sleep cycles per query
            response = logs.get_query_results(
                queryId=query_id
            )

        print(f"Records matched: {response['statistics']['recordsMatched']}")
        print("Wrting results...")

        for res in response['results']:

            user = 'Bob'
            notebook = 'Default'
            timestamp = '9999-01-01 00:00:00.000'

            for obj in res:
                try:
                    if obj['field'] == 'pth':
                        user, notebook = obj['value'].split(": ")
                    elif obj['field'] == 'day':
                        timestamp = obj['value']
                    else:
                        print("Unrecognized field: ", obj)
                except Exception as e:
                    print(f"Something went wrong with the parsing '{obj}': {e}")

            writer.writerow({'user': user, 'notebook': notebook, 'timestamp': timestamp})

        print("\n")
