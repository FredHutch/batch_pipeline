#!/bin/bash

aws s3 cp step1_picard/run_picard.py s3://fh-pi-meshinchi-s/SR/dtenenba-scripts/
aws s3 cp step2_kallisto/run_kallisto.py s3://fh-pi-meshinchi-s/SR/dtenenba-scripts/
aws s3 cp step3_pizzly/run_pizzly.py s3://fh-pi-meshinchi-s/SR/dtenenba-scripts/
