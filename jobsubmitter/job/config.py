import json
import logging
import os

from kubernetes import client
from hikaru.model.rel_1_21 import *

from jobsubmitter.job.base_manifests import base_executor, base_configmap
from jobsubmitter.job.nextflowconfigfile import NextflowConfigFile

logging.getLogger('kubernetes').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def make_cm_vol(params: dict[str, dict],
                client_id: str,
                ns: str,
                pvc_vol: Volume) -> tuple[ConfigMap, Volume]:
    """ Create a volume from parameter and executor ConfigMaps """
    cm = _make_parameter_cm(params, client_id, ns)
    result: Response = cm.createNamespacedConfigMap(namespace=ns)
    cm.metadata.name = result.obj.metadata.name  # update name metadata with generated name

    logger.debug("Merging k8s execution configuration and updating")
    cm.merge(_make_executor_cm(ns, pvc_vol))
    cm.immutable = True
    cm.update()

    return cm, Volume(name='config', configMap=ConfigMapVolumeSource(name=result.obj.metadata.name))


def adopt_object(job: Job, object) -> None:
    """ Set the parent of the object to the job instance that requires it.

     This simplifies k8s garbage collection once the job instance deletes itself."""
    logger.debug(f"Patching {object.metadata.name} (adopted by Job {job.metadata.name})")
    ow: OwnerReference = OwnerReference(apiVersion=job.apiVersion,
                                        kind="Job",
                                        name=job.metadata.name,
                                        uid=job.metadata.uid)
    object.metadata.ownerReferences = [ow]  # must be a list!
    object.update()


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
    # prepend the PVC mount path to the paths in the message
    # TODO: dynamically set PVC mount path
    target_genomes = []
    for file in params['target_genomes']:
        d = {}
        for k, v in file.items():
            if 'path' in k:
                v = os.path.join('/workspace', v)
            d.update({k: v})
        target_genomes.append(d)

    file_dict: dict[str, str] = {'input.json': json.dumps(target_genomes),
                                 'params.json': json.dumps(params['nxf_params_file'])}
    meta = _make_cm_meta(client_id, params, ns)
    return ConfigMap(data=file_dict, metadata=meta, immutable=False)


def _make_executor_cm(ns: str, pvc_vol: Volume) -> ConfigMap:
    """ Create an executor ConfigMap, unique to each pipeline run instance.

     The created ConfigMap describes _how_ the pipeline will execute.

     For example:
         - Which namespace to deploy worker pods to
         - What PVC to use for work
     """
    execution_params = {'k8s.storageClaimName': f"'{pvc_vol.persistentVolumeClaim.claimName}'",
                        'k8s.namespace': f"'{ns}'" }
    cm: ConfigMap = base_executor()
    configfile: NextflowConfigFile = NextflowConfigFile(cm.data['k8s.config'])
    cm.data['k8s.config'] = configfile.update(execution_params).data
    return cm

