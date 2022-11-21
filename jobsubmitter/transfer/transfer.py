import os
import subprocess
import logging
import time

import globus_sdk

logging.getLogger('globus_sdk').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
log_fmt = "%(name)s: %(asctime)s %(levelname)-8s %(message)s"
logging.basicConfig(level=logging.DEBUG,
                    format=log_fmt,
                    datefmt='%Y-%m-%d %H:%M:%S')


def create_local_endpoint(endpoint_name: str) -> tuple[str, str]:
    logger.debug(f"Creating endpoint: endpoint_name")
    process = subprocess.run(["globus", "gcp", "create", "mapped", endpoint_name, "--force-encryption"],
                             stdout=subprocess.PIPE)

    # example output:
    # Message:       Endpoint created successfully
    # Collection ID: uuid
    # Setup Key:     uuid
    out: list[str] = [x.decode("utf-8") for x in process.stdout.split(b"\n")]
    logger.debug(out[0])  # don't log secrets
    assert "Endpoint created successfully" in out[0]
    collection_id, setup_key = [x.split(":")[-1].strip() for x in out[1:] if x]

    return collection_id, setup_key


def setup_gpc(key: str, debug: bool = False) -> None:
    """ Set up globus personal connect with a key

    An open and active stdin is a _requirement_ for the globusconnectpersonal program.
    If one isn't available, you'll get a crash during setup with very unhelpful error messages.
    See: https://groups.google.com/a/globus.org/g/discuss/c/92Qdg6OdrFY.

    @param debug:
    @param key:
    @return:
    """
    logger.debug("Setting up Globus personal connect...")

    if debug:
        os.environ["GCP_DEBUG"] = "1"

    gcp_command: list[str] = ["globusconnectpersonal", "-setup", "--setup-key", key]

    # 1. open stdin pipe
    process = subprocess.Popen(gcp_command, shell=False, preexec_fn=os.setsid, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 2. wait for setup to complete
    time.sleep(30)

    # 3. get results and get rid of stdin now it's not needed
    process_stdout, process_stderr = process.communicate()
    return_code = process.wait()

    if return_code == 0:
        logger.debug("Globus personal connect configured :)")
        process.terminate()
    else:
        logger.critical(f"Globus personal connect set up failed, returned code {return_code}")
        logger.critical(f"stdout: {process_stdout}")
        logger.critical(f"stderr: {process_stderr}")
        process.terminate()
        raise SystemExit(1)

    # start globusconnectpersonal in a new process
    subprocess.Popen(["globusconnectpersonal", "-start"])


def authorise_transfer():
    logger.debug("Getting Globus authorisation")
    # the globus CLI understands environment variables
    # however, globus_sdk doesn't, so need to authorise for transfer
    client_id = os.getenv("GLOBUS_CLI_CLIENT_ID")
    client_key = os.getenv("GLOBUS_CLI_CLIENT_SECRET")
    client = globus_sdk.ConfidentialAppAuthClient(client_id, client_key)
    logger.debug("Authorised")
    return globus_sdk.ClientCredentialsAuthorizer(confidential_client=client,
                                                  scopes=[globus_sdk.scopes.TransferScopes.all])


def submit_transfer(source_endpoint_id: str, destination_endpoint_id: str) -> None:
    logger.debug("Submitting transfer request")
    tc = globus_sdk.TransferClient(authorizer=authorise_transfer())
    tdata = globus_sdk.TransferData(tc,
                                    source_endpoint_id,
                                    destination_endpoint_id,
                                    label="SDK example",
                                    encrypt_data=True,
                                    sync_level="checksum")
    source_dir = "/"
    dest_dir = os.getenv("LOCAL_DEST")  # TODO: use argparse?
    tdata.add_item(source_dir, dest_dir, recursive=True)
    # globus_sdk.services.transfer.errors.TransferAPIError: ('POST', 'https://transfer.api.globus.org/v0.10/transfer', 'Bearer', 409, 'GCDisconnectedException', "The Globus Connect Personal endpoint 'test (ad6432aa-69c2-11ed-8fd2-e9cb7c15c7d2)' is not currently connected to Globus", 'yrWr1Xkho')
    transfer_result = tc.submit_transfer(tdata)

    while not tc.task_wait(transfer_result["task_id"], timeout=60):
        logger.debug(f"Waiting for transfer {transfer_result['task_id']} to complete")


# TODO: give proper endpoint name? and cleanup?
# TODO: set up argparse
source_id = os.getenv("GLOBUS_SRC")
destination_id, setup_key = create_local_endpoint(endpoint_name="test")
setup_gpc(key=setup_key)
submit_transfer(source_id, destination_id)

