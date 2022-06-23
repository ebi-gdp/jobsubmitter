"""This module loads and configures the K8S objects necessary for a pgsc_calc instance to run.

Some K8S objects are static and loaded from local manifests (job/manifests/).

Some K8S objects (e.g. configMap volume) must be loaded from local manifests and then configured with JSON data.
"""

from ruamel.yaml import YAML
import importlib.resources
import logging
from kubernetes import client
from hikaru.model.rel_1_21 import *
from . import manifests

logging.getLogger('kubernetes').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def base_configmap() -> ConfigMap:
    """ Load the base ConfigMap from a K8S manifest """
    yaml: YAML = YAML()
    base_cm: str = importlib.resources.read_text(manifests, 'nxf-base.yaml')
    return ConfigMap.from_yaml(yaml.load(base_cm))


def base_job() -> Job:
    """ Load a base job object from a K8S Job manifest """
    yaml: YAML = YAML()
    nxf_driver: str = importlib.resources.read_text(manifests, 'pgsc-job.yaml')
    return Job.from_yaml(yaml.load(nxf_driver))


def make_cm_vol(params: dict[str, str],  # TODO: fix this type hint
                client_id: str,
                ns: str) -> tuple[ConfigMap, Volume]:
    """ Create a volume from a dynamic ConfigMap, unique to each pipeline run ID """

    # keys are file names that will be mounted in the volume
    file_dict: dict[str, str] = {'input.json': str(params['target_genomes']),
                                 'params.json': str(params['nxf_params_file'])}
    meta = make_cm_meta(client_id, params, ns)
    cm = ConfigMap(data=file_dict, metadata=meta, immutable=True)
    result: Response = cm.createNamespacedConfigMap(namespace=ns)
    cm.metadata.name=result.obj.metadata.name # update name metadata with generated name
    return cm, Volume(name='config', configMap=ConfigMapVolumeSource(name=result.obj.metadata.name))


def make_cm_meta(client_id: str, params: dict[str, str], ns: str) -> ObjectMeta:
    """ Set up the metadata for a ConfigMap """
    labels: dict = {'app': 'nextflow',
                    'submitter': client_id,
                    'run-id': params['id'],
                    'cm_type': 'volume'}

    return ObjectMeta(labels=labels,
                      namespace=ns,
                      generateName='nxf-configmap-vol-')


def adopt_configmap(job: Job, cm: ConfigMap) -> None:
    """ Make job instance parent of configmap to simplify garbage collection """

    ow: OwnerReference = OwnerReference(apiVersion=job.apiVersion,
                                        kind="Job",
                                        name=job.metadata.name,
                                        uid=job.metadata.uid)
    cm.metadata.ownerReferences = [ow]  # must be a list!
    logger.debug("Patching ConfigMap (adopted by Job)")
    logger.debug(cm)
    cm.update()


def make_shared_cm(ns: str) -> None:
    """ Ensure the shared ConfigMap is provisioned """
    base_cm: ConfigMap = base_configmap()
    try:
        base_cm.read(namespace=ns)
    except client.exceptions.ApiException:
        base_cm.create(namespace=ns)


def make_job_instance(params: dict, client_id: str, ns: str) -> tuple[ConfigMap, Job]:
    """ Provision a job instance with parameters from Kafka """
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
    cm, job = make_job_instance(params, client_id, ns)
    logger.debug("Submitting job to K8S")
    job.create(namespace=ns)
    logger.debug(job)
    adopt_configmap(job, cm)

    # TODO: update configmap
