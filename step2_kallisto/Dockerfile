# save image as fredhutch/pipeline_kallisto

FROM fredhutch/fredhutch-ubuntu:16.04_20171030

# aws, curl, git, and unzip are already installed
# so are python and python3 but no pip*

RUN curl -LO https://bootstrap.pypa.io/get-pip.py

RUN python3 get-pip.py

RUN pip install boto3 sh

RUN rm get-pip.py

RUN curl -LO https://github.com/pachterlab/kallisto/releases/download/v0.43.1/kallisto_linux-v0.43.1.tar.gz

RUN tar zxf kallisto_linux-v0.43.1.tar.gz

RUN cp kallisto_linux-v0.43.1/kallisto /usr/local/bin/

RUN rm -rf kallisto_linux-v0.43.1.tar.gz  kallisto_linux-v0.43.1

RUN curl -LO https://github.com/awslabs/aws-batch-helpers/archive/master.zip

RUN unzip master.zip

RUN cp aws-batch-helpers-master/fetch-and-run/fetch_and_run.sh /usr/local/bin/

RUN rm -rf master.zip aws-batch-helpers-master

ENTRYPOINT ["/usr/local/bin/fetch_and_run.sh"]
