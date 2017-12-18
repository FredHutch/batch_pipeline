# build as fredhutch/ls2:picard.2

FROM fredhutch/ls2:picard.1

USER root

RUN curl -LO https://bootstrap.pypa.io/get-pip.py

RUN python3 get-pip.py

RUN pip3 install boto3 sh

RUN rm get-pip.py

USER neo
