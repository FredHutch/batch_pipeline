#!/usr/bin/env python3
"""
a shell-script-like python script to run picard
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
        java_dir = "/home/neo/.local/easybuild/software/Java/1.8.0_92/bin"
        bam = "{}.bam".format(sample)
        r1 = "{}_r1.fq.gz".format(sample) # pylint: disable=invalid-name
        r2 = "{}_r2.fq.gz".format(sample) # pylint: disable=invalid-name
        # add java_dir to path
        os.environ['PATH'] += ":" + java_dir
        ebrootpicard = "/home/neo/.local/easybuild/software/picard/2.13.2-Java-1.8.0_92/"
        LOGGER.info("Downloading bam file...")
        if not os.path.exists(bam): # for testing TODO remove
            for line in aws("s3", "cp",
                            "s3://{}/SR/{}".format(bucket, bam), "."):
                print(line)
        # run picard, put output in file
        java = sh.java.bake(_iter=True, _err_to_out=True, _long_sep=" ")
        LOGGER.info("Running picard...")
        logfile = "{}_picard.stderr".format(sample)
        with open(logfile, "w") as plog:
            for line in java("-Xmx6g", "-Xms2g", "-jar",
                             "{}/picard.jar".format(ebrootpicard),
                             "SamToFastq", "QUIET=true",
                             "INCLUDE_NON_PF_READS=true",
                             "VALIDATION_STRINGENCY=SILENT",
                             "MAX_RECORDS_IN_RAM=250000", "I={}".format(bam),
                             "F={}".format(r1), "F2={}".format(r2)):
                LOGGER.info("picard: %s", line)
                plog.write(line)
                plog.flush()
                sys.stdout.flush()
        # copy picard output to S3
        LOGGER.info("Copying picard output to S3...")
        for item in [r1, r2]:
            for line in aws("s3", "cp",
                            item, "s3://{}/SR/picard_fq2/".format(bucket),
                            sse="AES256"):
                print(line)
        for line in aws("s3", "cp", logfile,
                        "s3://{}/SR/picard_fq2/".format(bucket), sse="AES256"):
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
