import importlib.resources

from hikaru.model.rel_1_21 import *
from ruamel.yaml import YAML

from jobsubmitter.job import manifests



def load_manifest(path: str) -> str:
    """ Grab local manifests and read them """
    return importlib.resources.read_text(manifests, path)


def base_job() -> Job:
    """ The Job object starts a nextflow controller pod that manages worker pods """
    return Job.from_yaml(YAML().load(load_manifest('pgsc-job.yaml')))


def base_executor() -> ConfigMap:
    """ The created ConfigMap describes _how_ the pipeline will execute """
    return ConfigMap.from_yaml(YAML().load(load_manifest('k8s-executor.yaml')))


def base_configmap() -> ConfigMap:
    """ The created ConfigMap describes _what_ the pipeline will execute. """
    return ConfigMap.from_yaml(YAML().load(load_manifest('nxf-base.yaml')))
