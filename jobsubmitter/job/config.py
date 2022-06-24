import importlib.resources
import logging

from hikaru.model.rel_1_21 import *
from kubernetes import client
from ruamel.yaml import YAML

from jobsubmitter.job import manifests
from jobsubmitter.job.nextflowconfigfile import NextflowConfigFile

logging.getLogger('kubernetes').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def make_executor_cm(params) -> ConfigMap:
    """ Overwrite parts of base executor config file with message parameters """
    k8s_config: str = base_executor().data['k8s.config']
    configfile: NextflowConfigFile = NextflowConfigFile(k8s_config)
    # TODO: .to_dict() -> merge keys -> .from_dict()
    return ConfigMap()


def base_executor() -> ConfigMap:
    """ Load the base ConfigMap that describes nextflow k8s execution parameters"""
    yaml: YAML = YAML()
    base_executor: str = importlib.resources.read_text(manifests, 'k8s-executor.yaml')
    return ConfigMap.from_yaml(yaml.load(base_executor))


def base_configmap() -> ConfigMap:
    """ Load the base ConfigMap from a K8S manifest """
    yaml: YAML = YAML()
    base_cm: str = importlib.resources.read_text(manifests, 'nxf-base.yaml')
    return ConfigMap.from_yaml(yaml.load(base_cm))


def make_cm_vol(params: dict[str, str],  # TODO: fix this type hint
                client_id: str,
                ns: str) -> tuple[ConfigMap, Volume]:
    """ Create a volume from a dynamic ConfigMap, unique to each pipeline run ID """

    # keys are file names that will be mounted in the volume
    file_dict: dict[str, str] = {'input.json': str(params['target_genomes']),
                                 'params.json': str(params['nxf_params_file'])}
    meta = make_cm_meta(client_id, params, ns)
    cm = ConfigMap(data=file_dict, metadata=meta, immutable=False)
    result: Response = cm.createNamespacedConfigMap(namespace=ns)
    cm.metadata.name=result.obj.metadata.name # update name metadata with generated name

    logger.debug("Merging k8s execution configuration...")
    cm.merge(base_executor())
    logger.debug(cm)
    # TODO: now set CM to immutable
    return cm, Volume(name='config', configMap=ConfigMapVolumeSource(name=result.obj.metadata.name))


def make_cm_meta(client_id: str, params: dict[str, str], ns: str) -> ObjectMeta:
    """ Create a metadata object for the ConfigMap """
    labels: dict = {'app': 'nextflow',
                    'submitter': client_id,
                    'run-id': params['id'],
                    'cm_type': 'volume'}

    return ObjectMeta(labels=labels,
                      namespace=ns,
                      generateName='nxf-configmap-vol-')


def adopt_configmap(job: Job, cm: ConfigMap) -> None:
    """ Set the parent of the ConfigMap to the job instance that requires it.

     This simplifies k8s garbage collection."""

    ow: OwnerReference = OwnerReference(apiVersion=job.apiVersion,
                                        kind="Job",
                                        name=job.metadata.name,
                                        uid=job.metadata.uid)
    cm.metadata.ownerReferences = [ow]  # must be a list!
    logger.debug("Patching ConfigMap (adopted by Job)")
    logger.debug(cm)
    cm.update()


def make_shared_cm(ns: str) -> None:
    """ Ensure the shared ConfigMap is provisioned in the namespace"""
    base_cm: ConfigMap = base_configmap()
    try:
        base_cm.read(namespace=ns)
    except client.exceptions.ApiException:
        base_cm.create(namespace=ns)
