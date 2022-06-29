import logging

from hikaru.model.rel_1_21 import *

from .base_manifests import base_job
from .config import make_cm_vol, adopt_configmap

logging.getLogger('kubernetes').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def submit_job(params, client_id, ns) -> None:
    """ Create the Job object and set the ConfigMap parent """
    cm: ConfigMap
    job: Job
    cm, job = _populate_job_instance(params, client_id, ns)
    logger.debug("Submitting job to K8S")
    job.create(namespace=ns)
    logger.debug(job)
    adopt_configmap(job, cm)


def _populate_job_instance(params: dict, client_id: str, ns: str) -> tuple[ConfigMap, Job]:
    """ Populate a loaded base job instance with parameters from Kafka """
    nxf_job: Job = base_job()
    cm: ConfigMap
    cm_vol: Volume
    cm, cm_vol = make_cm_vol(params, client_id, ns)
    volumes = nxf_job.spec.template.spec.volumes
    volumes[1] = cm_vol

    return cm, nxf_job
