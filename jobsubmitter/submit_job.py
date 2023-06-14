import logging
import argparse
from threading import Thread

import kubernetes

from jobsubmitter import config
from jobsubmitter.consume import create_consumer
from jobsubmitter.job.job import submit_job
from jobsubmitter.job.config import make_shared_cm
from jobsubmitter.watch import job_watcher

logger = logging.getLogger(__name__)
log_fmt = "%(name)s: %(asctime)s %(levelname)-8s %(message)s"


def parse_args(args=None) -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='Consume Kafka messages and launch jobs')
    parser.add_argument("--kafka_bootstrap_urls", help="Path to kafka bootstrap server",required=True)
    parser.add_argument("--client_id", help="Unique identifier of this client",required=True)
    parser.add_argument("--namespace", help="Namespace of provisioned jobs", required=True)
    parser.add_argument("--output_bucket", help="s3 root URL of output bucket", required=True)
    parser.add_argument("--local_config", help="Use local KUBECONFIG", action='store_true')
    parser.add_argument("--verbose", help="Chattier logs", action='store_true')
    return parser.parse_args(args)


def main(args=None):
    args = parse_args(args)
    config.NAMESPACE = args.namespace
    config.OUTPUT_BUCKET = args.output_bucket

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG,
                            format=log_fmt,
                            datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logging.basicConfig(level=logging.INFO,
                            format=log_fmt,
                            datefmt='%Y-%m-%d %H:%M:%S')

    logger.info(args)
    bootstrap_list = args.kafka_bootstrap_urls.strip().split(",")

    if args.local_config:
        kubernetes.config.load_kube_config()
    else:
        kubernetes.config.load_incluster_config()

    make_shared_cm()  # ensure the shared configmap is provisioned at startup

    watch_thread = Thread(target=job_watcher, kwargs={'bootstrap_servers': bootstrap_list}, daemon=True)
    watch_thread.start()
    assert watch_thread.is_alive()

    consumer = create_consumer(args.client_id, bootstrap_list)

    if not consumer.topics():
        logger.critical("Can't connect to kafka broker")
        raise RuntimeError()
    else:
        logger.info("Ready and listening for job requests")

    for message in consumer:
        make_shared_cm() # make sure cm is present
        assert watch_thread.is_alive()
        params = message.value

        if params == {}:  # messages that fail validation are returned empty
            logging.error(message)
            continue
        else:
            logging.info(message)

        submit_job(params, args.client_id)


if __name__ == '__main__':
    main()
