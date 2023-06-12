import json
import time

import logging

from kafka import KafkaProducer
from kubernetes import client

logger = logging.getLogger(__name__)


def job_watcher(bootstrap_servers):
    producer = KafkaProducer(bootstrap_servers=bootstrap_servers,
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))

    if not producer.bootstrap_connected():
        logger.critical("Can't connect to kafka broker")
        raise RuntimeError()
    else:
        logger.debug("Producer connected to bootstrap server")
        logger.info(f"Job watch starting")

    api_client = client.BatchV1Api()
    known_jobs: dict[str, str] = {}

    while True:
        logger.info("Getting list of jobs")
        jobs = api_client.list_namespaced_job('intervene-dev')

        if len(jobs.items) == 0:
            logger.debug("Found no jobs in job list, sleeping 1 minute")
            known_jobs: dict[str, str] = _prune_jobs(known_jobs, jobs)
            time.sleep(60)
        else:
            logger.debug("Found jobs in job list")
            for job in jobs.items:
                if 'pgsc-calc' in job.metadata.name:
                    logger.debug(f"Found pgsc-calc job {job.metadata.name}")
                    run_id: str
                    status: str
                    uid, run_id, status = _get_job_status(job)
                    pruned_jobs: dict[str, str] = _prune_jobs(known_jobs, jobs)
                    known_jobs: dict[str, str] = _update_jobs(producer=producer, pipeline_id=uid, run_id=run_id, status=status, known_jobs=pruned_jobs)
                else:
                    logger.debug("Job not pgsc-calc, ignoring")
                    continue
            logger.debug("Sleeping 1 minute")
            time.sleep(60)


def _get_job_status(job) -> tuple[str, str, str]:
    uid = job.metadata.labels.get('run-id')
    run_id = job.metadata.name
    status = ''
    if job.status.start_time is not None:
        status = 'started'

    if job.status.succeeded is not None:
        status = 'completed'
    elif job.status.failed is not None:
        status = 'failed'

    return uid, run_id, status


def _update_jobs(producer, pipeline_id: str, run_id: str, status: str, known_jobs: dict[str, str]) -> dict[str, str]:
    if run_id in known_jobs:
        if known_jobs[run_id] == status:
            logger.info(f"Message already sent for job {run_id}")
            return known_jobs
        else:
            logger.info(f"Status change for job {run_id}")
            _send_message(producer=producer, status=status, run_id=run_id, pipeline_id=pipeline_id)
    else:
        logger.info(f"New job found: {run_id}")
        _send_message(producer=producer, status=status, run_id=run_id, pipeline_id=pipeline_id)

    return known_jobs | {run_id: status}


def _prune_jobs(known_jobs: dict[str, str], job_list) -> dict[str, str]:
    # If a job is known but missing from the job list, it's been cleaned up, so remove it
    job_names: set = {x.metadata.name for x in job_list.items}
    missing_jobs = set(known_jobs.keys()).difference(job_names)
    if missing_jobs:
        for x in missing_jobs:
            logger.debug(f"Removing {x} from known jobs (cleaned up by K8S)")
            del known_jobs[x]
    else:
        logger.debug("No jobs need to be pruned from known jobs")
    return known_jobs


def _send_message(producer, status: str, run_id: str, pipeline_id: str) -> None:
    message = {'status': status.upper(), 'pipelineId': pipeline_id, 'outdir': ""}
    logger.debug(f"Sending message for job {run_id}: {message}")
    producer.send('pipeline-status', message)
