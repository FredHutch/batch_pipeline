#!/usr/bin/env python3
"""
a shell-script-like python script to run pizzly
in AWS batch
"""

import os
import logging
import shutil
import sys
import traceback

import sh

def is_on_aws():
    "check if we are running on aws"
    return os.getenv("HOSTNAME").startswith("ip-")

def check_vars():
    """
    Make sure all needed environment variables are set.
    Return True if this is an array job.
    """
    if not any([os.getenv("SAMPLE_NAME"), os.getenv("LIST_OF_SAMPLES")]):
        print("SAMPLE_NAME must be set for single-jobs.")
        print("LIST_OF_SAMPLES must be set for array jobs.")
        sys.exit(1)
    if os.getenv("AWS_BATCH_JOB_ARRAY_INDEX") and os.getenv("SAMPLE_NAME"):
        print("Don't set SAMPLE_NAME in an array job.")
        sys.exit(1)
    if os.getenv("AWS_BATCH_JOB_ARRAY_INDEX") and not os.getenv("LIST_OF_SAMPLES"):
        print("This is an array job but LIST_OF_SAMPLES is not set!")
        sys.exit(1)
    if not os.getenv("BUCKET_NAME"):
        print("BUCKET_NAME must be set!")
        sys.exit(1)
    if os.getenv("AWS_BATCH_JOB_ARRAY_INDEX") and os.getenv("LIST_OF_SAMPLES"):
        return True
    if os.getenv("SAMPLE_NAME") and not os.getenv("AWS_BATCH_JOB_ARRAY_INDEX"):
        return False
    print("Something is wrong with your environment variables!")
    sys.exit(1)
    return False # unreachable but makes pylint happy

def main(): # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    "do the work"
    LOGGER.info("hostname is %s", os.getenv("HOSTNAME"))
    is_array_job = check_vars()
    job_id = os.getenv("AWS_BATCH_JOB_ID").replace(":", "-")
    # use a scratch directory that no other jobs on this instance will overwrite
    scratch_dir = "/scratch/{}_{}".format(job_id, os.getenv("AWS_BATCH_JOB_ATTEMPT"))
    if is_on_aws(): # no scratch when developing locally
        LOGGER.info("Using scratch directory %s", scratch_dir)
        os.makedirs(scratch_dir) # should not exist
        os.chdir(scratch_dir)
    exitcode = 0
    try:
        bucket = os.getenv("BUCKET_NAME")
        if is_array_job:
            sample_index = int(os.getenv("AWS_BATCH_JOB_ARRAY_INDEX"))
            LOGGER.info("This is an array job and the index is %d.", sample_index)
            samples = os.getenv("LIST_OF_SAMPLES").split(",")
            # get sample from list of samples using job array index
            sample = samples[sample_index].strip()
        else:
            sample = os.getenv("SAMPLE_NAME").strip()
        LOGGER.info("Sample is %s.", sample)
        aws = sh.aws.bake(_iter=True, _err_to_out=True, _out_bufsize=3000)
        LOGGER.info("Downloading fusion file...")
        if not os.path.exists("fusion.txt"): # for testing TODO remove
            for line in aws("s3", "cp",
                            "s3://{}/SR/kallisto_out/{}/fusion.txt".format(bucket, sample), "."):
                print(line)
        # create output dir
        os.makedirs(sample, exist_ok=True)
        # run kallisto, put output in file
        pizzly = sh.pizzly.bake(_iter=True, _err_to_out=True, _long_sep=" ")
        LOGGER.info("Running pizzly...")
        pdir = "/usr/local/pizzly_test_files"
        with open("{}/pizzly.out".format(sample), "w") as plog:
            # FIXME this needs to change:
            for line in pizzly("fusion.txt", k=31,
                               gtf="{}/Homo_sapiens.GRCh37.87.gtf.gz".format(pdir),
                               align_score=2, insert_size=400,
                               fasta="{}/Homo_sapiens.GRCh37.cdna.all.fa".format(pdir),
                               output="{}/some_prefix".format(sample),):
                LOGGER.info("pizzly: %s", line)
                plog.write(line)
                plog.flush()
                sys.stdout.flush()
        # copy pizzly output to S3
        LOGGER.info("Copying all pizzly output to S3...")
        for line in aws("s3", "cp", "--sse", "AES256", "--recursive", "--include", "*",
                        sample, "s3://{}/SR/pizzly_out/{}/".format(bucket, sample)):
            print(line)
        LOGGER.info("Completed without errors.")
    # handle errors
    except Exception: # pylint: disable=broad-except
        exitcode = 1
        traceback.print_exc()
        LOGGER.info("Failed!")
    finally:
        if is_on_aws():
            LOGGER.info("Removing scratch directory...")
            shutil.rmtree(scratch_dir, True)
        # exit with appropriate code so Batch knows
        # whether job SUCCEEDED or FAILED
        LOGGER.info("Exiting with exit code %s.", exitcode)
        sys.exit(exitcode)

if __name__ == "__main__":
    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT)
    LOGGER = logging.getLogger()
    LOGGER.setLevel(logging.INFO)
    main()
