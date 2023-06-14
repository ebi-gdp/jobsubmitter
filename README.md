# Job submitter

`jobsubmitter` is part of the INTERVENE platform backend. `jobsubmitter` is a python service that:

* Listens for job requests, sent as Kafka messages with a JSON payload
* Validates the JSON payload against bundled JSON schema
* Creates `pgsc_calc` nextflow job and associated resources to do polygenic risk score calculation
* Monitors submitted jobs and reports state changes to the backend via Kafka

The nextflow job uses the [Kubernetes executor](https://www.nextflow.io/docs/latest/kubernetes.html#kubernetes). 

Each job has a sandboxed persistent volume claim to handle inter-process (cross-pod) communication. 

The job submitter doesn't [use Fusion](https://nextflow.io/blog/2023/the-state-of-kubernetes-in-nextflow.html) yet.

## Usage

To deploy on a Kubernetes cluster quickly:

```
$ kubectl apply -f jobsubmitter.yaml
```

To run locally:

```
$ git clone https://github.com/ebi-gdp/jobsubmitter.git
$ cd jobsubmitter
$ poetry shell
$ submit_job --kafka_bootstrap_urls localhost:9092 \
    --client_id test_id \
    --namespace test \
    --output_bucket test
```

* `--kafka_boostrap_urls`: An URL that points to a Kafka service
* `--client_id`: A human readable label for the kafka consumer
* `--namespace`: The Kubernetes namespace you want to deploy the job submitter and jobs to
* `--output_bucket`: The root URL of the bucket you'd like to publish results to. e.g:
  * `s3://results_bucket` -> `--output_bucket results_bucket`
  * Individual workflow results are published to `s3://results_bucket/<WORKFLOW_ID_FROM_JSON_MESSAGE>` 
