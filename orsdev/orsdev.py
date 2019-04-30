# -*- coding: utf-8 -*-

import click
from datetime import datetime

@click.group()
def main():
    """Entry point for the program."""

    pass

@main.command()
@click.argument('')


def parse_args():
    parser = argparse.ArgumentParser(
        description='ORS development tester')

    parser.add_argument(
        'test_server',
        help='The test server holding your development environment',
        type=str)

    parser.add_argument(
        'outfile',
        help=
        'The full path to your output PBF/XML file. Note, the file ending determines the format.',
        type=str)

    parser.add_argument(
        '-p',
        '--provider',
        help='Choose the provider of the proprietary dataset. Default tomtom.',
        choices=['tomtom'],
        default='tomtom')

    # Just a flag, no values to pass
    parser.add_argument('-r',
                        '--report',
                        help='Print out report to stdout.',
                        action='store_true')

    return parser.parse_args()


if __name__ == '__main__':
    main()
