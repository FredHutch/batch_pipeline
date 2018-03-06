# save image as fredhutch/pipeline_pizzly

# build me like this:

# aws s3 cp s3://fh-pi-meshinchi-s/SR/GRCh37/Homo_sapiens.GRCh37.87.gtf .
# aws s3 cp s3://fh-pi-meshinchi-s/SR/GRCh37/Homo_sapiens.GRCh37.cdna.all.fa .
# docker build -t fredhutch/pipeline_pizzly .

FROM fredhutch/fredhutch-ubuntu:16.04_20171030

# aws, curl, git, and unzip are already installed
# so are python and python3 but no pip*

RUN curl -LO https://bootstrap.pypa.io/get-pip.py

RUN python3 get-pip.py

RUN pip3 install boto3 sh

RUN rm get-pip.py

RUN curl -LO curl -LO https://github.com/pmelsted/pizzly/releases/download/v0.37.3/pizzly_linux.tar.gz

RUN tar zxf pizzly_linux.tar.gz

RUN cp pizzly /usr/local/bin/

RUN rm -rf pizzly_linux.tar.gz LICENSE README.md

RUN mv test /usr/local/pizzly_test_files

ADD Homo_sapiens.GRCh37.87.gtf.gz /usr/local/pizzly_test_files/

ADD Homo_sapiens.GRCh37.cdna.all.fa /usr/local/pizzly_test_files/

RUN curl -LO https://github.com/awslabs/aws-batch-helpers/archive/master.zip

RUN unzip master.zip

RUN cp aws-batch-helpers-master/fetch-and-run/fetch_and_run.sh /usr/local/bin/

RUN rm -rf master.zip aws-batch-helpers-master

ENTRYPOINT ["/usr/local/bin/fetch_and_run.sh"]
