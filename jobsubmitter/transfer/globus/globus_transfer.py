#!/usr/bin/env python3

import argparse
import atexit
import logging
import os
import subprocess
import time

import globus_sdk
from globus_sdk.services.transfer import errors

logging.getLogger('globus_sdk').setLevel(logging.WARNING)  # globus_sdk is chatty
logger = logging.getLogger(__name__)


def create_local_endpoint(endpoint_name: str) -> tuple[str, str]:
    """ Create a local endpoint using the globus CLI """
    logger.info(f"Creating endpoint: {endpoint_name}")
    process = subprocess.run(["globus", "gcp", "create", "mapped", endpoint_name, "--force-encryption"],
                             stdout=subprocess.PIPE)

    # example stdout:
    # Message:       Endpoint created successfully
    # Collection ID: uuid
    # Setup Key:     uuid
    out: list[str] = [x.decode("utf-8") for x in process.stdout.split(b"\n")]
    logger.debug(out[0])  # don't log secrets
    assert "Endpoint created successfully" in out[0]
    collection_id, setup_key = [x.split(":")[-1].strip() for x in out[1:] if x]

    return collection_id, setup_key


def setup_gpc(key: str, debug: bool = False) -> None:
    """ Set up globus personal connect (GPC) with a setup key, and start a GPC process

    An open and active stdin is a _requirement_ for the globusconnectpersonal program.
    If one isn't available, you'll get a crash during setup with very unhelpful error messages.
    See: https://groups.google.com/a/globus.org/g/discuss/c/92Qdg6OdrFY.
    """
    logger.info("Setting up Globus personal connect")

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
        logger.info("Globus personal connect configured :)")
        process.terminate()
    else:
        logger.critical(f"Globus personal connect set up failed, returned code {return_code}")
        logger.critical(f"stdout: {process_stdout}")
        logger.critical(f"stderr: {process_stderr}")
        process.terminate()
        raise SystemExit(1)

    # start globusconnectpersonal in a new process
    logger.info("Starting globus personal connect process")
    subprocess.Popen(["globusconnectpersonal", "-start"])
    wait_until_connected()


def wait_until_connected(wait: int = 10):
    process = subprocess.run(["globusconnectpersonal", "-status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    status: str = " ".join(process.stdout.split(b'\n')[0].decode("utf-8").split())

    if "Globus Online: connected" not in status:
        logger.info("Waiting for globus to connect")
        time.sleep(wait)
        wait_until_connected()
    else:
        logger.info("Globus connected")
        logger.debug(process.stdout.decode("utf-8"))


def authorise_transfer():
    logger.info("Getting Globus authorisation")
    # the globus CLI understands environment variables
    # however, globus_sdk doesn't, so need to authorise for transfer
    client_id = os.getenv("GLOBUS_CLI_CLIENT_ID")
    client_key = os.getenv("GLOBUS_CLI_CLIENT_SECRET")
    client = globus_sdk.ConfidentialAppAuthClient(client_id, client_key)
    logger.info("Authorised")
    return globus_sdk.ClientCredentialsAuthorizer(confidential_client=client,
                                                  scopes=[globus_sdk.scopes.TransferScopes.all])


def submit_transfer(source_endpoint_id: str, destination_endpoint_id: str, dest_dir: str) -> None:
    tc = globus_sdk.TransferClient(authorizer=authorise_transfer())
    tdata = globus_sdk.TransferData(tc,
                                    source_endpoint_id,
                                    destination_endpoint_id,
                                    label="IGS4EU transfer",
                                    encrypt_data=True,
                                    sync_level="checksum")
    source_dir = "/"  # sync everything (the root of the source endpoint)
    tdata.add_item(source_dir, dest_dir, recursive=True)

    logger.info("Submitting transfer request")
    logger.info(f"Source endpoint id: {source_endpoint_id}")
    logger.info(f"Destination endpoint id: {destination_endpoint_id}")
    transfer_result = _retry_transfer(tc=tc, tdata=tdata, i=0)
    task_id = transfer_result["task_id"]

    logger.info(f"Transfer request {task_id} submitted. Waiting...")
    while not tc.task_wait(transfer_result["task_id"], timeout=60):
        logger.info(f"Waiting for transfer {transfer_result['task_id']} to complete")


def _retry_transfer(tc, tdata, i):
    try:
        return tc.submit_transfer(tdata)
    except errors.TransferAPIError as exc:
        if i > 5:
            logger.debug("Giving up waiting to reconnect, goodbye")
            raise
        else:
            # sometimes globus personal connect takes a little while to reconnect to globus
            logger.debug(f"TransferAPIError, waiting for GPC to automatically reconnect... {i}")
            time.sleep(5)
            i += 1
            _retry_transfer(tc, tdata, i)


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Transfer")
    parser.add_argument("--endpoint_name", dest="endpoint_name", required=True)
    parser.add_argument("--source_endpoint_id", dest="source_id", required=True)
    parser.add_argument("--destination_dir", dest="dest_dir", required=True)
    parser.add_argument("--verbose", dest="verbose", action="store_true")
    return parser.parse_args()


def cleanup(endpoint_id: str):
    logger.info(f"Cleaning up: deleting local endpoint {endpoint_id}")
    tc = globus_sdk.TransferClient(authorizer=authorise_transfer())
    tc.delete_endpoint(endpoint_id)
    logger.info("Cleaning up: stopping globus personal connect process")
    subprocess.run(["globusconnectpersonal", "-stop"])


def transfer():
    args = parse_args()
    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    log_fmt = "%(name)s: %(asctime)s %(levelname)-8s %(message)s"
    logging.basicConfig(level=log_level,
                        format=log_fmt,
                        datefmt='%Y-%m-%d %H:%M:%S')

    logger.info(f"Endpoint name: {args.endpoint_name}")
    logger.info(f"Source endpoint id: {args.source_id}")
    logger.info(f"Destination dir: {args.dest_dir}")

    destination_id, setup_key = create_local_endpoint(endpoint_name=args.endpoint_name)
    atexit.register(cleanup, endpoint_id=destination_id)
    setup_gpc(key=setup_key)
    submit_transfer(source_endpoint_id=args.source_id, destination_endpoint_id=destination_id,
                    dest_dir=args.dest_dir)

    logger.info("Transfer completed. Goodbye :)")


if __name__ == "__main__":
    transfer()
