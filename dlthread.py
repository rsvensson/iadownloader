import os
import requests
import threading
import time
from datetime import datetime
from queue import Queue
from tqdm import tqdm


# Graciously stolen and adapted from Anurag Uniyal @ https://stackoverflow.com/a/18883984

class DownloadThread(threading.Thread):
    def __init__(self, queue: Queue):
        super(DownloadThread, self).__init__()
        self.queue = queue
        self.daemon = True

    def _get_filename(self, url: str):
        filename = requests.utils.unquote(url.split("/")[-1])
        if url.find("/compress/") != -1:
            # User requested the compressed archive
            filename += ".zip"
        return filename

    def _get_mtime_from_str(self, last_mod: str) -> int:
        """Converts a webserver's response header's last-modified string into a Unix time-style integer"""

        try:
            mod_date = datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S %Z").timetuple()
            return int(time.mktime(mod_date))
        except TypeError:
            return int(time.mktime(datetime.now().timetuple()))

    def _get_resume_pos(self, dlpath: str, url: str, compressed: bool) -> int:
        """Handles resuming an existing file if incomplete."""

        resume_pos = 0

        if os.path.exists(dlpath) and os.path.isfile(dlpath):
            filename = dlpath.split("/")[-1]
            with requests.get(url, stream=True, allow_redirects=True) as r:
                r.raise_for_status()
                local_size = os.path.getsize(dlpath)
                remote_size = int(r.headers.get("content-length", 0))
                if not compressed:
                    local_time = int(os.path.getmtime(dlpath))
                    remote_time = self._get_mtime_from_str(r.headers.get("last-modified"))
                    if local_time == remote_time and local_size > 0:
                        print(f"{filename} already downloaded. Skipping.\n")
                        return -1
                else:
                    # The compressed archive's mtime is created at the time of download
                    if local_size == remote_size and local_size > 0:
                        print(f"{filename} already downloaded. Skipping.\n")
                        return -1
                resume_pos = local_size

        return resume_pos

    def run(self):
        while True:
            dldir, url = self.queue.get()
            try:
                os.makedirs(dldir, exist_ok=True)
                self.download_url(dldir, url)
            except Exception as e:
                print(f"Error: {e}")
            self.queue.task_done()

    def download_url(self, dldir: str, url: str):
        filename = self._get_filename(url)
        compressed = True if filename.endswith(".zip") else False
        dlpath = os.path.join(dldir, filename)
        resume_pos = self._get_resume_pos(dlpath, url, compressed)

        if resume_pos == -1:  # File already downloaded
            return
        elif resume_pos > 0:
            print(f"Resuming {filename} at {resume_pos} bytes.")
        with requests.get(url, stream=True, allow_redirects=True,
                          headers={"Range": f"bytes={resume_pos}-"}) as r:
            r.raise_for_status()

            total_size = int(r.headers.get("content-length", 0))
            block_size = 8192
            progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True, leave=False)
            progress_bar.set_description(filename)  # Prefix filename to output
            mod_time = self._get_mtime_from_str(r.headers.get("last-modified"))
            mode = "wb" if resume_pos == 0 else "ab"

            with open(dlpath, mode) as fd:
                for block in r.iter_content(block_size):
                    progress_bar.update(len(block))
                    fd.write(block)
            progress_bar.close()

        # Set last modified time
        os.utime(dlpath, (mod_time, mod_time))
        print(f"{filename}: Done")
