import json
import logging

from hikaru.model.rel_1_21 import *

from jobsubmitter import config
from jobsubmitter.job.base_manifests import base_job
from jobsubmitter.job.config import make_cm_vol, adopt_object

from jobsubmitter.transfer.init_container import build_init_containers

logging.getLogger('kubernetes').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def submit_job(params, client_id) -> None:
    """ Create the Job object and set the ConfigMap parent """
    cm: ConfigMap
    job: Job

    # create configmap for transfer initContainer
    transfer_cm = _make_transfer_cm(params)

    # get a list of initcontainers, and assign the new configmap
    volume, init_containers = build_init_containers(transfer_cm.metadata.name)

    # create configmap for main job, and add the transfer volume
    cm, job = _populate_job_instance(params['pipeline_param'], client_id, volume)
    job.spec.template.spec.initContainers = init_containers


    job.create(namespace=config.NAMESPACE)
    logger.debug(f"Submitted job {job.metadata.name} to K8S")

    # set job as owner of auxiliary objects (configmap / pvc)
    # when job dies, these objects must die too
    pvc = PersistentVolumeClaim().read(name=volume.persistentVolumeClaim.claimName, namespace=config.NAMESPACE)
    [adopt_object(job, x) for x in [cm, transfer_cm, pvc]]


def _make_transfer_cm(params: dict) -> ConfigMap:
    """ The transfer config map sets the globus source endpoint ID and the local destination

    - The local destination must be the mountPath of the attached PVC
    - local_dest must have read / write permissions for the globus-client user
    - the volume-mount-hack initContainer fixes PVC permissions
    """
    meta = ObjectMeta(namespace=config.NAMESPACE, generateName="transfer-", labels={'app': 'transfer'})
    globus_base_url = "https://g-1504d5.dd271.03c0.data.globus.org" if config.NAMESPACE == "dev" else "https://g-8b9225.dd271.03c0.data.globus.org"
    d = {'GLOBUS_GUEST_COLLECTION_ID': params['globus_details']['guest_collection_id'],
         'GLOBUS_BASE_URL': globus_base_url,
         'JOB_MESSAGE': json.dumps(params)}
    cm = ConfigMap(immutable=True, metadata=meta, data=d)
    logger.info(f"Creating transfer configmap: {d}")
    cm.create()
    return cm

def _populate_job_instance(params: dict, client_id: str,pvc_vol: Volume) -> tuple[ConfigMap, Job]:
    """ Populate a loaded base job instance with parameters from Kafka """
    nxf_job: Job = base_job()
    cm: ConfigMap
    cm_vol: Volume
    cm, cm_vol = make_cm_vol(params, client_id, pvc_vol)
    volumes = nxf_job.spec.template.spec.volumes
    # set up persistent data shared across transfer initContainer + job
    volumes[0] = pvc_vol
    # mount config map too
    volumes[1] = cm_vol

    # TODO: add version to parameters, update consumer ID?
    nxf_job.metadata.labels = nxf_job.metadata.labels | {'run-id': params['id'], 'version': '1.3'}

    return cm, nxf_job



