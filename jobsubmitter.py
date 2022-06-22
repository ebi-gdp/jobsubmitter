import logging
import argparse
from jobsubmitter.consume import create_consumer

from jobsubmitter.job.provision import make_job_instance

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(message)s')


def parse_args(args=None) -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='Consume Kafka messages and launch jobs')
    parser.add_argument("--kafka_bootstrap_urls", help="Path to kafka bootstrap server",required=True)
    parser.add_argument("--client_id", help="Unique identifier of this client",required=True)
    parser.add_argument("--namespace", help="Namespace of provisioned jobs", required=True)

    return parser.parse_args(args)


def main(args=None):
    args = parse_args(args)
    logger.debug(args)
    bootstrap_list = args.kafka_bootstrap_urls.strip().split(",")

    consumer = create_consumer(args.client_id, bootstrap_list)

    for message in consumer:
        params = message.value

        if params == {}:
            continue  # messages that fail validation are returned empty

        logger.debug(params)
        job = make_job_instance(params=params,
                                client_id=args.client_id,
                                ns=args.namespace)

        job.createNamespacedJob(args.namespace)


if __name__ == '__main__':
    main()
