"""This module loads and configures the K8S objects necessary for a pgsc_calc instance to run.

Some K8S objects are static and loaded from local manifests (job/manifests/).

Some K8S objects (e.g. configMap volume) must be loaded from local manifests and then configured with JSON data.
"""

from ruamel.yaml import YAML
import importlib.resources
import logging
from kubernetes import config, client
from hikaru.model.rel_1_21 import *
from . import manifests

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


def make_cm_vol(k8s_client: client.ApiClient,
                job: Job,
                params: dict[str, str],
                client_id: str,
                ns: str) -> Volume:
    """ Create a volume from a dynamic ConfigMap, unique to each pipeline run ID """

    # keys are file names that will be mounted in the volume
    file_dict: dict[str, str] = {'input.json': str(params['target_genomes']),
                                 'params.json': str(params['nxf_params_file'])}
    meta = make_cm_meta(client_id, params)
    cm = ConfigMap(data=file_dict, metadata=meta, immutable=True)
    logger.debug(cm)
    cm.set_client(k8s_client)
    result: Response = cm.createNamespacedConfigMap(namespace=ns)
    return Volume(name='config', configMap=ConfigMapVolumeSource(name=result.obj.metadata.name))


def make_cm_meta(client_id: str, params: dict[str, str]) -> ObjectMeta:
    """ Set up the metadata for a ConfigMap """
    labels: dict = {'app': 'nextflow',
                    'submitter': client_id,
                    'run-id': params['id'],
                    'cm_type': 'volume'}

    return ObjectMeta(labels=labels,
                      generateName='nxf-configmap-vol-')


def set_cm_ownership(job: Job) -> OwnerReference:
    """ Update configmap with an owner. Can only happen _after_ job creation. """

    return OwnerReference(apiVersion=job.apiVersion,
                          kind="Job",
                          name=job.metadata.name,
                          uid=job.metadata.uid)


def make_job_instance(params: dict, client_id: str, ns: str) -> Job:
    """ Provision a job instance with parameters from Kafka """
    config.load_incluster_config()
    api_client = client.ApiClient()

    try:
        base_cm: ConfigMap = base_configmap()
        base_cm.read(namespace=ns)
    except client.exceptions.ApiException:
        base_cm.create(namespace=ns)

    nxf_job: Job = base_job()

    cm_vol: Volume = make_cm_vol(api_client, nxf_job, params, client_id, ns)
    volumes = nxf_job.spec.template.spec.volumes
    volumes[1] = cm_vol
    logger.debug(nxf_job)

    return nxf_job
