# Job submitter

`jobsubmitter` is part of the INTERVENE platform backend. `jobsubmitter` is a python service that:

* Listens for job requests, sent as Kafka messages with a JSON payload
* Validates the JSON payload against bundled JSON schema
* Creates `pgsc_calc` nextflow job and associated resources to do polygenic risk score calculation
* Monitors submitted jobs and reports state changes to the backend via Kafka

The nextflow job uses the [Kubernetes executor](https://www.nextflow.io/docs/latest/kubernetes.html#kubernetes). 

Each job has a sandboxed persistent volume claim to handle inter-process (cross-pod) communication. 

The job submitter doesn't [use Fusion](https://nextflow.io/blog/2023/the-state-of-kubernetes-in-nextflow.html) yet.
