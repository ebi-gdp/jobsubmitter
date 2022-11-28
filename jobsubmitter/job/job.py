import logging

from hikaru.model.rel_1_21 import *

from .base_manifests import base_job
from .config import make_cm_vol, adopt_configmap

from jobsubmitter.transfer.init_container import build_init_containers

logging.getLogger('kubernetes').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def submit_job(params, client_id, ns) -> None:
    """ Create the Job object and set the ConfigMap parent """
    cm: ConfigMap
    job: Job

    # create configmap for transfer initContainer
    transfer_cm = _make_transfer_cm(params['globus_details'])

    # get a list of initcontainers, and assign the new configmap
    volume, init_containers = build_init_containers(transfer_cm.metadata.name)

    # create configmap for main job, and add the transfer volume
    cm, job = _populate_job_instance(params['pipeline_param'], client_id, ns, volume)
    job.spec.template.spec.initContainers = init_containers

    logger.debug("Submitting job to K8S")
    job.create(namespace=ns)
    logger.debug(job)

    # patch config map
    adopt_configmap(job, cm)

    # TODO: adopt other config map
    # TODO: adopt pvc


def _make_transfer_cm(params: dict, local_dest: str = '/home/globus-client/data') -> ConfigMap:
    """ The transfer config map sets the globus source endpoint ID and the local destination

    - The local destination must be the mountPath of the attached PVC
    - local_dest must have read / write permissions for the globus-client user
    - the volume-mount-hack initContainer fixes PVC permissions
    """
    meta = ObjectMeta(namespace="intervene-dev", generateName="transfer-", labels={'app': 'transfer'})
    d = {'globus_src': params['shared_endpoint_id'] } | { 'local_dest': local_dest}
    cm = ConfigMap(immutable=True, metadata=meta, data=d)
    logger.info(f"Creating transfer configmap: {d}")
    cm.create()
    return cm

def _populate_job_instance(params: dict, client_id: str, ns: str, pvc_vol: Volume) -> tuple[ConfigMap, Job]:
    """ Populate a loaded base job instance with parameters from Kafka """
    nxf_job: Job = base_job()
    cm: ConfigMap
    cm_vol: Volume
    cm, cm_vol = make_cm_vol(params, client_id, ns)
    volumes = nxf_job.spec.template.spec.volumes
    # set up persistent data shared across transfer initContainer + job
    volumes[0] = pvc_vol
    # mount config map too
    volumes[1] = cm_vol

    return cm, nxf_job



