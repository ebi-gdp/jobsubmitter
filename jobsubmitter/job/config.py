import logging

from kubernetes import client
from hikaru.model.rel_1_21 import *

from jobsubmitter.job.base_manifests import base_executor, base_configmap, base_job
from jobsubmitter.job.nextflowconfigfile import NextflowConfigFile

logging.getLogger('kubernetes').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def make_cm_vol(params: dict[str, dict],
                client_id: str,
                ns: str) -> tuple[ConfigMap, Volume]:
    """ Create a volume from parameter and executor ConfigMaps """
    cm = _make_parameter_cm(params, client_id, ns)
    result: Response = cm.createNamespacedConfigMap(namespace=ns)
    cm.metadata.name = result.obj.metadata.name  # update name metadata with generated name

    logger.debug("Merging k8s execution configuration and updating")
    cm.merge(_make_executor_cm(params, ns))
    cm.immutable = True
    cm.update()

    return cm, Volume(name='config', configMap=ConfigMapVolumeSource(name=result.obj.metadata.name))


def adopt_configmap(job: Job, cm: ConfigMap) -> None:
    """ Set the parent of the ConfigMap to the job instance that requires it.

     This simplifies k8s garbage collection once the job instance deletes itself."""
    ow: OwnerReference = OwnerReference(apiVersion=job.apiVersion,
                                        kind="Job",
                                        name=job.metadata.name,
                                        uid=job.metadata.uid)
    cm.metadata.ownerReferences = [ow]  # must be a list!
    logger.debug("Patching ConfigMap (adopted by Job)")
    logger.debug(cm)
    cm.update()


def make_shared_cm(ns: str) -> None:
    """ Ensure the shared ConfigMap is provisioned in the namespace

    The ConfigMap describes environment variables shared across all job instances """
    try:
        cm: ConfigMap = base_configmap()
        cm.update(namespace=ns)  # always synchronise shared configmap
    except client.exceptions.ApiException:
        logger.debug("Creating base configmaps")
        cm.create(namespace=ns)


def _make_cm_meta(client_id: str, params: dict[str, str], ns: str) -> ObjectMeta:
    """ Create a metadata object for the ConfigMap """
    labels: dict = {'app': 'nextflow',
                    'submitter': client_id,
                    'run-id': params['id'],
                    'cm_type': 'volume'}

    return ObjectMeta(labels=labels,
                      namespace=ns,
                      generateName='nxf-vol-')


def _make_parameter_cm(params, client_id, ns) -> ConfigMap:
    """ Create a parameter ConfigMap, unique to each pipeline run instance.

     The created ConfigMap desribes _what_ the nextflow pipeline will execute.

     For example:
        - Which polygenic scores to calculate
        - What input data to use
        - Pipeline settings such as LiftOver
     """
    # keys are file names that will be mounted in the volume
    file_dict: dict[str, str] = {'input.json': str(params['target_genomes']),
                                 'params.json': str(params['nxf_params_file'])}
    meta = _make_cm_meta(client_id, params, ns)
    return ConfigMap(data=file_dict, metadata=meta, immutable=False)


def _make_executor_cm(d: dict, ns: str) -> ConfigMap:
    """ Create an executor ConfigMap, unique to each pipeline run instance.

     The created ConfigMap describes _how_ the pipeline will execute.

     For example:
         - Which namespace to deploy worker pods to
         - What PVC to use for work
     """

    # PVC name should very rarely change, but if it does change pull it from the job manifest
    execution_params = {'k8s.storageClaimName': _get_pvc_name(),
                        'k8s.namespace': f"'{ns}'" }
    cm: ConfigMap = base_executor()
    configfile: NextflowConfigFile = NextflowConfigFile(cm.data['k8s.config'])
    cm.data['k8s.config'] = configfile.update(execution_params).data
    return cm


def _get_pvc_name() -> str:
    """ Get the PVC name of the working area from the base job manifest """
    workdir_pvc: str = base_job().find_by_name('persistentVolumeClaim')[0].path
    claim: str = base_job().object_at_path(workdir_pvc).claimName
    return f"'{claim}'"
