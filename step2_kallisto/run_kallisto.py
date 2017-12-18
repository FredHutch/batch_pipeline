#!/usr/bin/env python3
"""
a shell-script-like python script to run kallisto
in AWS batch
"""

import os
import logging
import sys
import traceback

import sh

def check_vars():
    """
    Make sure all needed environment variables are set.
    Return True if this is an array job.
    """
    # print("SAMPLE_NAME is {}".format(os.getenv("SAMPLE_NAME")))
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
    is_array_job = check_vars()
    job_id = os.getenv("AWS_BATCH_JOB_ID").replace(":", "-")
    # use a scratch directory that no other jobs on this instance will overwrite
    scratch_dir = "/scratch/{}_{}".format(job_id, os.getenv("AWS_BATCH_JOB_ATTEMPT"))
    if os.getenv("HOSTNAME").startswith("ip-"): # no scratch when developing locally
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
        index = "GRCh37.87.idx"
        fastqs = []
        aws = sh.aws.bake(_iter=True, _err_to_out=True, _out_bufsize=3000)
        # get fastq files
        LOGGER.info("Downloading fastq files...")
        for i in range(1, 3):
            fastq = "{}_r{}.fq.gz".format(sample, i)
            fastqs.append(fastq)
            if not os.path.exists(fastq): # for testing TODO remove
                for line in aws("s3", "cp", "s3://{}/SR/picard_fq2/{}".format(bucket, fastq), "."):
                    print(line)
        r1 = fastqs[0] # pylint: disable=invalid-name
        r2 = fastqs[1] # pylint: disable=invalid-name
        # get index file
        LOGGER.info("Downloading index file...")
        if not os.path.exists(index): # for testing, TODO remove
            for line in aws("s3", "cp", "s3://{}/SR/{}".format(bucket, index), "."):
                print(line)
        # create output dir
        os.makedirs(sample, exist_ok=True)
        # run kallisto, put output in file
        kallisto = sh.kallisto.bake(_iter=True, _err_to_out=True)
        LOGGER.info("Running kallisto...")
        with open("{}/kallisto.out".format(sample), "w") as klog:
            print("outfile is open")
            for line in kallisto('quant', '-i', index, '-o',
                                 sample, '-b', 30, '--fusion',
                                 '--rf-stranded', r1, r2):
                print("something")
                print(line)
                klog.write(line)
                klog.flush()
                sys.stdout.flush()
        # copy kallisto output to S3
        LOGGER.info("Copying all kallisto output to S3...")
        for line in aws("s3", "cp", "--sse", "AES256", "--recursive", "--include", "*",
                        sample, "s3://{}/SR/kallisto_out/{}/".format(bucket, sample)):
            print(line)
        LOGGER.info("Completed without errors.")
    # handle errors
    except Exception: # pylint: disable=broad-except
        exitcode = 1
        traceback.print_exc()
        LOGGER.info("Failed!")
    finally:
        # exit with appropriate code so Batch knows
        # whether job SUCCEEDED or FAILED
        LOGGER.info("Exiting with exit code %s.", exitcode)
        sys.exit(exitcode)

if __name__ == "__main__":
    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT)
    LOGGER = logging.getLogger()
    LOGGER.setLevel(logging.INFO)
    LOGGER.critical("hi there")
    main()
