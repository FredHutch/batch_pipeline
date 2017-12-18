#!/usr/bin/env python3
"""
main workflow class, etc.

Run me like this:

python3 main.py --queue=q-queue-name --bucket-name=a-bucket-name \
  --pipeline-name='a-name-for-this-pipeline' --sample-list-file=afilename

Where `afilename` is a file containing a list of sample names, one
per line.

"""

import os
import sys
import warnings

import boto3

with warnings.catch_warnings():
    warnings.filterwarnings('ignore', ".*psycopg2.*", )
    import sciluigi # FIXME silence warning this causes

class WF(sciluigi.WorkflowTask):
    "workflow class"
    queue = sciluigi.Parameter()
    bucket_name = sciluigi.Parameter()
    pipeline_name = sciluigi.Parameter()
    sample_list_file = sciluigi.Parameter()

    def workflow(self):
        step1 = self.new_task('step1', StepOneJobRunner, queue=self.queue,
                              bucket_name=self.bucket_name,
                              pipeline_name=self.pipeline_name,
                              sample_list_file=self.sample_list_file)

        step2 = self.new_task('step2', StepTwoJobRunner, queue=self.queue,
                              bucket_name=self.bucket_name,
                              pipeline_name=self.pipeline_name,
                              sample_list_file=self.sample_list_file)


        step2.in_step1 = step1.out_jobid


        step3 = self.new_task('step3', StepThreeJobRunner, queue=self.queue,
                              bucket_name=self.bucket_name,
                              pipeline_name=self.pipeline_name,
                              sample_list_file=self.sample_list_file)

        step3.in_step2 = step2.out_jobid
        return step3

class BatchJobRunner(sciluigi.Task):
    "common runner class"
    job_id = None
    job_def_name = None
    job_def_revision = None
    script_url = None
    queue = sciluigi.Parameter()
    bucket_name = sciluigi.Parameter()
    pipeline_name = sciluigi.Parameter()
    sample_list_file = sciluigi.Parameter()

    job_name = None
    submit_args = None

    def run(self):
        self.job_def_revision = get_latest_jobdef_revision(self.job_def_name)
        jobdef = self.job_def_name + ":" + str(self.job_def_revision)
        with open(self.sample_list_file) as filehandle:
            samples = filehandle.readlines()
        samples = [x.strip() for x in samples]
        samples = [x.replace(".bam", "") for x in samples]
        sample_list = ",".join(samples)
        array_size = len(samples)
        if array_size < 2:
            print("You must specify at least two samples to run an array job!")
            sys.exit(1)
        env = [
            dict(name="BUCKET_NAME", value=self.bucket_name),
            dict(name="LIST_OF_SAMPLES", value=sample_list),
            dict(name="BATCH_FILE_S3_URL", value=self.script_url)
        ]


        self.submit_args = dict(jobQueue=self.queue,
                                arrayProperties=dict(size=array_size),
                                jobDefinition=jobdef,
                                containerOverrides=dict(environment=env))


class StepOneJobRunner(BatchJobRunner):
    "runner for first step in pipeline"
    job_def_name = "pipeline-step1-picard"
    # FIXME task should automatically copy script to S3 before running
    script_url = "s3://fh-pi-meshinchi-s/SR/dtenenba-scripts/run_picard.py"
    def out_jobid(self):
        "return job id"
        return sciluigi.TargetInfo(self, "step1.out")
    def run(self):
        super(StepOneJobRunner, self).run()
        self.submit_args['jobName'] = self.pipeline_name + "-picard-step-" + USER
        response = BATCH.submit_job(**self.submit_args)
        self.job_id = response['jobId']
        with self.out_jobid().open('w') as filehandle:
            filehandle.write(self.job_id)
        print("Job ID for picard parent job is {}.".format(self.job_id))


class StepTwoJobRunner(BatchJobRunner):
    "runner for second step in pipeline"
    job_def_name = "pipeline-step2-kallisto"
    script_url = "s3://fh-pi-meshinchi-s/SR/dtenenba-scripts/run_kallisto.py"
    in_step1 = None
    def out_jobid(self):
        "return job id"
        return sciluigi.TargetInfo(self, "step2.out")
    def run(self):
        super(StepTwoJobRunner, self).run()
        self.submit_args['jobName'] = self.pipeline_name + "-kallisto-step-" + USER
        with self.in_step1().open() as in_f: # pylint: disable=not-callable
            job_id = in_f.read()
        self.submit_args['dependsOn'] = [dict(jobId=job_id, type="N_TO_N")]
        response = BATCH.submit_job(**self.submit_args)
        self.job_id = response['jobId']
        with self.out_jobid().open('w') as filehandle:
            filehandle.write(self.job_id)
        print("Job ID for kallisto parent job is {}.".format(self.job_id))


class StepThreeJobRunner(BatchJobRunner):
    "runner for third step in pipeline"
    job_def_name = "pipeline-step3-pizzly"
    script_url = "s3://fh-pi-meshinchi-s/SR/dtenenba-scripts/run_pizzly.py"
    in_step2 = None
    def out_jobid(self):
        "return job id"
        return sciluigi.TargetInfo(self, "step3.out")
    def run(self):
        super(StepThreeJobRunner, self).run()
        self.submit_args['jobName'] = self.pipeline_name + "-pizzly-step-" + USER
        with self.in_step2().open() as in_f: # pylint: disable=not-callable
            job_id = in_f.read()
        self.submit_args['dependsOn'] = [dict(jobId=job_id, type="N_TO_N")]
        response = BATCH.submit_job(**self.submit_args)
        self.job_id = response['jobId']
        print("Job ID for kallisto parent job is {}.".format(self.job_id))

        self.job_id = response['jobId']
        with self.out_jobid().open('w') as filehandle:
            filehandle.write(self.job_id)
        print("Job ID for pizzly parent job is {}.".format(self.job_id))





def get_latest_jobdef_revision(jobdef_name): # FIXME handle pagination
    "get the most recent revision for a job definition"
    results = \
      BATCH.describe_job_definitions(jobDefinitionName=jobdef_name)['jobDefinitions']
    if not results:
        raise ValueError("No job definition called {}.".format(jobdef_name))
    return max(results, key=lambda x: x['revision'])['revision']



def main():
    "handle args and run workflow"
    # remove old files
    print("Removing step files from previous runs...")
    for i in range(1, 4):
        stepfile = "step{}.out".format(i)
        if os.path.exists(stepfile):
            os.remove(stepfile)

    sciluigi.run_local(main_task_cls=WF)

if __name__ == "__main__":
    BATCH = boto3.client("batch")
    USER = os.getenv("USER")
    main()
