from ruamel.yaml import YAML
import importlib.resources
import logging

from hikaru.model.rel_1_21 import *
from . import manifests
from .config import make_cm_vol, adopt_configmap

logging.getLogger('kubernetes').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def base_job() -> Job:
    """ Load a job object from a K8S manifest (containing some dummy parameters) """
    yaml: YAML = YAML()
    nxf_driver: str = importlib.resources.read_text(manifests, 'pgsc-job.yaml')
    return Job.from_yaml(yaml.load(nxf_driver))


def populate_job_instance(params: dict, client_id: str, ns: str) -> tuple[ConfigMap, Job]:
    """ Populate a loaded base job instance with parameters from Kafka """
    nxf_job: Job = base_job()
    cm: ConfigMap
    cm_vol: Volume
    cm, cm_vol = make_cm_vol(params, client_id, ns)
    volumes = nxf_job.spec.template.spec.volumes
    volumes[1] = cm_vol

    return cm, nxf_job


def submit_job(params, client_id, ns) -> None:
    """ Create the Job object and set the ConfigMap parent """
    cm: ConfigMap
    job: Job
    cm, job = populate_job_instance(params, client_id, ns)
    logger.debug("Submitting job to K8S")
    job.create(namespace=ns)
    logger.debug(job)
    adopt_configmap(job, cm)
