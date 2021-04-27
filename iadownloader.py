#!/usr/bin/env python

from dlthread import DownloadThread

import argparse
import json
import os
import requests
import sys
from lxml import html
from queue import Queue


dlurl = "https://archive.org/download/"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL or path to json/csv file")
    parser.add_argument("-c", "--compressed",
                        help="Get the compressed archive download instead of the individual files",
                        action="store_true")
    parser.add_argument("-o", "--output_dir", help="Path to output directory", default=os.getcwd())
    parser.add_argument("-t", "--threads", help="Number of simultaneous downloads (maximum of 10)",
                        type=int, default=4)
    parser.add_argument("-T", "--torrent", help="Only download the torrent file if available",
                        action="store_true")

    args = parser.parse_args()

    if not str(args.url).startswith("http://") and not str(args.url).startswith("https://") \
       and not str(args.url).endswith(".json") and not str(args.url).endswith(".csv"):
        print("Error: Invalid URL or json/csv file.")
        sys.exit(1)

    return args


def json2list(path: str) -> list:
    """
    Parses a json file from IA's advanced search into a list of urls.
    :param path: Path to the json file.
    :return: List of download urls.
    """

    urls = list()
    try:
        text = open(path, "r").read()
    except FileNotFoundError:
        print(f"Error: No such json file: {path}")
        sys.exit(1)
    text = text.replace("callback(", "")  # Remove non-json leading text
    data = json.loads(text.rstrip(")"))  # Don't include the trailing ")"
    docs = data["response"]["docs"]

    for entry in docs:
        urls.append(dlurl + entry["identifier"])

    return urls


def csv2list(path: str) -> list:
    """
    Parses a csv file from IA's advanced search into a list of urls.
    :param path: Path to the csv file.
    :return: List of download urls.
    """

    urls = list()
    try:
        with open(path, "r") as fd:
            for line in fd.readlines():
                if line.find('"identifier"') != -1:
                    continue  # Skip header
                line = line.replace('"', '')  # Remove surrounding quote marks
                urls.append(dlurl + line.rstrip("\n"))  # Remove potential newlines
    except FileNotFoundError:
        print(f"Error: No such csv file: {path}")
        sys.exit(1)

    return urls


def get_download_links(url: str, compressed: bool, torrent: bool) -> list:
    """
    Returns the links in a download url.
    """

    # Convert the details page to the download page
    url = url.replace("/details/", "/download/")

    if compressed and not torrent:  # It doesn't make sense to get the compressed file if torrent is also true
        return [url.replace("/download/", "/compress/")]

    page = requests.get(url)
    webpage = html.fromstring(page.content)
    rawlinks = webpage.xpath("//a/@href")
    links = list()

    for link in rawlinks:
        if torrent:
            if link.endswith(".torrent"):
                links.append(dlurl + url.split("/")[-1] + "/" + link)
        else:
            if link.startswith("http://")  or link.startswith("https://") \
               or link.find("#maincontent") != -1 or link.find("/details/") != -1 \
               or link.endswith("/"):
               # Skip links that are not for file downloads
               continue
            links.append(dlurl + url.split("/")[-1] + "/" + link)

    return links


def enqueue(downloads: dict, numthreads: int = 4):
    # Be reasonable
    if numthreads > 10:
        print("Too many threads. Setting to 10.")
        numthreads = 10

    queue = Queue()
    for dlpath in downloads.keys():
        for link in downloads[dlpath]:
            queue.put((dlpath, link))

    for i in range(numthreads):
        t = DownloadThread(queue)
        t.start()

    queue.join()


def main():
    args = parse_args()
    downloads = dict()

    if args.url.startswith("http://") or args.url.startswith("https://"):
        links = get_download_links(args.url, args.compressed, args.torrent)
        downloads[args.output_dir] = links
        enqueue(downloads, args.threads)
        return
    elif args.url.endswith(".csv"):
        urls = csv2list(args.url)
    elif args.url.endswith(".json"):
        urls = json2list(args.url)
    else:
        print("Something went wrong")
        sys.exit(1)

    print("Fetching download links...")
    for i, url in enumerate(urls):
        print(f"\r{i+1}/{len(urls)}", end="")
        if (not args.compressed) or (args.compressed and args.torrent):  # Ignore the compressed bool if torrent is set
            dldir = os.path.join(args.output_dir, url.split("/")[-1])
        else:
            dldir = args.output_dir
        links = get_download_links(url, args.compressed, args.torrent)
        downloads[dldir] = links
    print()

    enqueue(downloads, args.threads)

if __name__ == "__main__":
    main()
