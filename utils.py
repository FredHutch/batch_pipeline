#!/usr/bin/env python3

"""
A utility to do the following:

1) Given a parent job ID, get the status of all child jobs, along with their
  IDs, sample names, and log stream names.
2) Given a parent job id and a sample name, find out how long the whole pipeline took
   for that sample.

This code uses the mongodb database of batch transition events. We don't use
the AWS Batch API because Batch only keeps job information around for 24 hours
after the job completes.

The environment variable MONGO_URL must be set for this code to work.

"""

import json
from operator import itemgetter
import re
import sys

from urllib.parse import quote_plus, urlparse
from collections import defaultdict

import pymongo


def get_pipeline_time(coll, parent_job_id, sample_name): # pylint: disable=too-many-locals
    "get total execution time for a single sample"
    summary = coll.find_one({"jobId": parent_job_id})
    # start_time = summary['timestamp']
    job_name = summary['jobName']
    overall_job_name = None
    segs = job_name.split("-")
    timestamp_regex = re.compile("^[0-9]{14}$")
    for i, seg in enumerate(segs):
        if timestamp_regex.match(seg):
            newsegs = segs[0:i+1]
            overall_job_name = "-".join(newsegs)
    list_of_samples = \
      [x for x in summary['container']['environment']
       if x['name'] == 'LIST_OF_SAMPLES'][0]['value'].split(",")
    sample_index = list_of_samples.index(sample_name)

    job_name_regex = re.compile("^{}-".format(overall_job_name))
    child_job_regex = re.compile(":")
    child_jobs = coll.find({"jobName": job_name_regex, "jobId": child_job_regex,
                            "$or": [{"status": "FAILED"},
                                    {"status": "SUCCEEDED"},
                                    {"status": "PENDING"}]})
    filtered_child_jobs = []
    for child_job in child_jobs:
        child_id = int(child_job['jobId'].split(':')[-1])
        if child_id == sample_index:
            filtered_child_jobs.append(child_job)
    # filtered_child_jobs contains more items than I expect. I expect it to have
    # (1 pending event + 1 ending event (success or failure) ) * the number of steps,
    # so for a 3-step pipeline, (1 + 1) * 3 = 6 (but I got 20.)
    # I think it's ok though, we still only care about the first and last ones.
    min0 = min(filtered_child_jobs, key=lambda x: x['timestamp'])
    max0 = max(filtered_child_jobs, key=lambda x: x['timestamp'])
    delta = max0['timestamp'] - min0['timestamp']

    print(delta)



def get_child_info(coll, parent_job_id):
    "get information about child jobs"
    summary = coll.find({"jobId": parent_job_id}).sort([("timestamp", -1)])
    result = dict(_parent_job_id=parent_job_id, children=[])
    list_of_samples = None
    for i, rec in enumerate(summary):
        if i == 0:
            # print("Overall summary:")
            # print(rec['arrayProperties']['statusSummary'])
            list_of_samples = \
              [x for x in rec['container']['environment']
               if x['name'] == 'LIST_OF_SAMPLES'][0]['value'].split(",")
            result['_overall_summary'] = rec['arrayProperties']['statusSummary']
        else:
            break
    # get child jobs

    regex = re.compile("^{}:".format(parent_job_id))
    children = coll.find({"jobId": regex})
    child_dict = defaultdict(lambda: [])
    for child in children:
        child_dict[child['jobId']].append(child)

    for value in list(child_dict.values()):
        last = max(value, key=lambda x: x['timestamp'])
        item = dict(child_id=int(last['jobId'].split(":")[-1]), status=last['status'])
        lsn = last['attempts'][-1]['container']['logStreamName']
        item['logStreamName'] = lsn
        item['sample'] = list_of_samples[item['child_id']]

        result['children'].append(item)
    result['children'] = sorted(result['children'], key=itemgetter('child_id'))
    print(json.dumps(result, indent=4, sort_keys=True))

def get_coll():
    "get collection"
    # OMG, credentials in code! That's bad! But these are readonly credentials
    # and the database is only accessible inside our network.
    parsed_url = urlparse("mongodb://readonly:Mq$61Iu2hng2@mydb.fhcrc.org:32100/batch_events")
    segs = str(parsed_url.netloc).split(":")
    netloc_segs = segs[1].split('@')
    netloc_segs[0] = quote_plus(netloc_segs[0]) # escape password
    segs[1] = "@".join(netloc_segs)
    url2 = "{}://{}{}".format(parsed_url.scheme, ":".join(segs), parsed_url.path)
    client = pymongo.MongoClient(url2)
    db0 = client.batch_events
    coll = db0.events
    return coll


def main():
    "do the work"
    coll = get_coll()
    if len(sys.argv) == 1:
        help0 = """
Pipeline utilities.

Supply a parent job ID to get the status, sample names, and log stream names of each child job.

Supply a parent job ID and a sample name to get the total execution time of
the full pipeline for that sample. The parent job id supplied can be for
any one of the pipeline steps. Results look like this:

9 days, 8:07:06.543210

...which means 9 days, 8 hours, 7 minutes, 6 seconds, 543 milliseconds, and 210 microseconds.
The days portion is omitted if the job took less than one day.
        """
        print(help0.strip())
    elif len(sys.argv) == 2:
        get_child_info(coll, sys.argv[1])
    elif len(sys.argv) == 3:
        get_pipeline_time(coll, sys.argv[1], sys.argv[2])




if __name__ == '__main__':
    main()
