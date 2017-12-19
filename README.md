# AWS Batch Example Array Job Pipeline

## Overview


Many scientific tasks are sequential, multi-step processes.
The steps are dependent upon each other; that is, step 2 cannot
proceed without the output from step 1.

This example implements one such process, consisting of three tasks.

### Task 1:

* Download a BAM file from S3
* Run [Picard](https://broadinstitute.github.io/picard/) on it,
  producing two `fastq` files.
* Upload  `fastq` files to S3.

### Task 2:

* Download the `fastq` files (produced in Task 1) from S3
* Run [kallisto](https://pachterlab.github.io/kallisto/) on them.
* Upload the output (a `fusion.txt`) file to S3.

### Task 3:

* Download the `fusion.txt` file (produced in Task 2) from S3.
* Run [pizzly](https://github.com/pmelsted/pizzly) on it.
* Upload the output (??) to S3.


Using AWS Batch [Array Jobs](https://docs.aws.amazon.com/batch/latest/userguide/array_jobs.html),
we can kick off any number of these tasks at once.

## Implementation

The implementation consists of several parts.

### 'Batch-side' scripts

This refers to the scripts that are run on AWS Batch (as opposed to
other scripts running on your local computer which orchestrate Batch
jobs).

Often these 'batch-side' scripts are written in the bash shell scripting
language. In this example, they are written in Python, for several reasons:

* Complexity is reduced by using a single language both on the Batch
  side and on the orchestration side.
* Bash syntax can be bewildering and finicky, even to experienced users.
  Python is readable. Even people who do not know the language can guess
  the basic gist of much Python code.

The python scripts do use the excellent [sh](https://amoffat.github.io/sh/)
package, which makes shell-script-like programming in Python very easy.

In this example, the 'batch-side' scripts are in the
[step1_picard](step1_picard/), [step2_kallisto](step2_kallisto/),
and [step3_pizzly](step3_pizzly/) directories.

### Fetch And Run

The mechanism used to run the scripts on Batch is
the [Fetch & Run](https://aws.amazon.com/blogs/compute/creating-a-simple-fetch-and-run-aws-batch-job/)
script. This script is set as the `ENTRYPOINT` of your Docker container.
Then, when you start a Batch job, you pass (as an environment variable)
the [S3](https://aws.amazon.com/s3/) URL of your 'batch-side' script, and it is
run.

### Job Submission

This pipeline consists of three array jobs.
The first job, running the `picard` step, has no dependencies.
The second job, running the `kallisto` step, depends on the first job.
The third job, running the `pizzly` step, depends on the second job.

So the first job must be started so that we can get its job ID, and we then
use that ID in the second job to declare a dependency on the first one,
and likewise for the third.

We can pass a list of samples to the jobs, as a comma-delimited
environment variable (called `LIST_OF_SAMPLES`).
Assuming we passed a list of 10 samples, 10 `picard` jobs would start
right away. When one of these jobs finishes, the corresponding `kallisto`
job will begin.

These jobs are started in the [main.py](main.py) script.

This script uses the [sciluigi](https://github.com/pharmbio/sciluigi)
workflow system to define the tasks and dependencies.
`sciluigi` may be overkill for such a simple pipeline, but it illustrates
that any workflow tool may be used to orchestrate AWS Batch jobs.
Also, as the complexity of jobs increases, the use of such a tool
may be increasingly appropriate.

#### Example

Install this repository  as follows:

```
git clone https://github.com/FredHutch/batch_pipeline.git
cd batch_pipeline
```

Install [pipenv](https://docs.pipenv.org/#install-pipenv-today) if it is
not already installed.

Install dependencies and activate your virtual environment:

```
pipenv shell
```

Make sure you have obtained [S3](https://teams.fhcrc.org/sites/citwiki/SciComp/Pages/Getting%20AWS%20Credentials.aspx)
credentials and the [additional permissions](https://fredhutch.github.io/aws-batch-at-hutch-docs/)
needed to run AWS Batch.

You need to run some one-time steps (see the next section) which
will eventually be automated. Once those have been done, you can
submit your job:

```
python3 main.py --queue=mixed --bucket-name=<YOUR_BUCKET_NAME> \
  --pipeline-name='first-test-pipeline' --sample-list-file=./sample_list.txt

```

Where `sample_list.txt` is a file containing a list of sample names,
one per line.



### Possible enhancements


* Factor out common code in the 'batch-side' scripts. This would require
  putting the common code in a library, and passing the `fetch & run` script
  a zip file (containing all the code) instead of a single script. This
  requires some development and test time.
* Create a common Dockerfile to be the parent of all the Dockerfiles used
  in this example.
* Enhance the example so that all the preliminary work, which is
  currently done manually, can be done automatically
  from within the `sciluigi` workflow.
  These preliminary steps include:
  * Building and pushing the Docker images.
  * Creating the job definitions for each job.
  * Copying the batch-side scripts to S3 before starting a job.

See the [issues](https://github.com/FredHutch/batch_pipeline/issues) page
for more detail.

### Questions, comments, fixes?

File an [issue](https://github.com/FredHutch/batch_pipeline/issues/new)
or send a [pull request](https://github.com/FredHutch/batch_pipeline/pulls).
