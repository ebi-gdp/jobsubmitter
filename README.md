# Job submitter

`jobsubmitter` is part of the INTERVENE platform backend. `jobsubmitter` is a python service that:

* Listens for job requests, sent as Kafka messages with a JSON payload
* Validates the JSON payload against bundled JSON schema
* Creates `pgsc_calc` nextflow job and associated resources to do polygenic risk score calculation
* Monitors submitted jobs and reports state changes to the backend via Kafka
