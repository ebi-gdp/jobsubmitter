import importlib.resources
import itertools
import logging
import pathlib

import hikaru
from hikaru.model.rel_1_21 import *
from ruamel.yaml import YAML

from jobsubmitter.transfer import manifests

from kubernetes import config
from kubernetes.client import ApiClient

logger = logging.getLogger(__name__)


def build_init_containers(config_map_name) -> tuple[Volume, list[Container]]:
    # 1. read pod from manifest
    logger.info("Reading transfer pod from manifest")
    pod = _load_pod()

    # 2. set config map name
    pod.spec.containers[0].env = _update_env_var_cm_ref(pod, config_map_name)

    # 3. make a PVC for initContainer (PVC name is generated)
    pvc = _instantiate_pvc()
    pvc.create()
    logger.info(f"PVC {pvc.metadata.name} created in {pvc.metadata.namespace}")

    # add a volumeMount PVC to pod
    volume_mount, volume = _instantiate_volumes(pvc)
    pod.spec.containers[0].volumeMounts = [volume_mount]

    # order is important: volume mount fix must run first
    init_containers: list[Container] = [_load_volume_mount_fix(), pod.spec.containers[0]]
    return volume, init_containers


def _instantiate_pvc() -> PersistentVolumeClaim:
    logger.info("Making ReadWriteMany Persistent Volume Claim")
    # TODO: make namespace dynamic
    meta = ObjectMeta(namespace="intervene-dev", generateName="transfer-", labels={'app': 'transfer'})
    pv = PersistentVolumeClaim()
    pv.metadata = meta
    pv_spec = PersistentVolumeClaimSpec()
    pv_spec.accessModes = ["ReadWriteMany"]
    # TODO: RWX is a pain
    pv_spec.storageClassName = "example-nfs-ssd"
    # TODO: make storage size dynamic. from globus?
    pv_spec.resources = ResourceRequirements(requests={'storage': '40Gi'})
    pv.spec = pv_spec
    return pv


def _instantiate_volumes(pvc) -> tuple[VolumeMount, Volume]:
    logger.info("Creating volume mount")
    vm = VolumeMount(name="vol-1", mountPath="/data")
    logger.debug("Creating volume with PVC source")
    pvcvs = PersistentVolumeClaimVolumeSource(claimName=pvc.metadata.name)
    vol = Volume(name="vol-1", persistentVolumeClaim=pvcvs)
    return vm, vol


def _update_env_var_cm_ref(pod: Pod, config_map_name: str) -> list[EnvVar]:
    """ Update the ConfigMap reference in non-secret environment variables """
    logger.info(f"Updating transfer pod config map name: {config_map_name}")
    env_list = pod.object_at_path(['spec', 'containers', 0, 'env'])
    # GLOBUS_SECRET* env vars are managed by secret
    # the secret is managed independently of the job submitter
    not_secrets: list[bool] = ["GLOBUS_SECRET" not in x.name for x in env_list]
    secrets = list(itertools.compress(env_list, [not x for x in not_secrets]))
    not_secret_env = list(itertools.compress(env_list, not_secrets))

    return secrets + [_update_configmap_selector(x, config_map_name) for x in not_secret_env]


def _update_configmap_selector(env, config_map_name) -> EnvVar:
    """ Extract the ConfigMapKeySelector from an EnvVar, update the ConfigMap name it refers to, and return an EnVar """
    key_ref = env.object_at_path(["valueFrom", "configMapKeyRef"])
    key_ref.name = config_map_name
    env.valueFrom = EnvVarSource(key_ref)
    return env


def _load_pod():
    """ Load the transfer pod manifest.

    After populating PVC mount names and config map names, the container will be extracted. The extracted container is
    used as an initContainer. """
    with importlib.resources.files(manifests).joinpath('transfer.yaml') as f:
        yaml = YAML()
        return Pod.from_yaml(yaml.load(f))


def _load_volume_mount_fix():
    """ This weird little container fixes the volume mount permissions of the newly created PVC

    The PVC is for transferred data and the nextflow working directory. It should have good IOPS (fast SSD).

    Explanation/justification of this hack:
        - By default the new PVC is owned by root
        - Changing permissions automatically with a securityContext isn't supported by the NFS driver
        - We need NFS for RWX support (nextflow pre-requisite)
        - The transfer container can't run as root (globusconnectpersonal _needs_ a user, and bad idea anyway)

    So this hack is the best way forward! Unless we make a different RW PVC without NFS in the future.

    This function returns a container should run as an initContainer, before any other initContainers.
    """
    logger.info("Reading volume mount fix container manifest")
    # note: assumes that the PVC-backed volume is called vol-1
    with importlib.resources.files(manifests).joinpath('volume_mount.yaml') as f:
        yaml = YAML()
        return Container.from_yaml(yaml.load(f))



