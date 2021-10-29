from __future__ import print_function
from time import sleep

import errno
import subprocess
import sys
import tempfile
import os
import time
import uuid

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

__all__ = ["load_ipython_extension"]


JUPYTER_HTML_TEMPLATE = """
<iframe id='snakeviz-{uuid}' frameborder=0 seamless width='100%' height='1000'></iframe>
<script>document.getElementById("snakeviz-{uuid}").setAttribute("src", "http://" + document.location.hostname + ":{port}{path}")</script>
"""
def file_to_base64(filepath):
    """
    Returns the content of a file as a Base64 encoded string.
    :param filepath: Path to the file.
    :type filepath: str
    :return: The file content, Base64 encoded.
    :rtype: str
    """
    import base64
    with open(filepath, 'rb') as f:
        encoded_str = base64.b64encode(f.read())
    return encoded_str

def getUrlWithHtml(file):
   return "data:text/html;base64," + file_to_base64(file).decode('utf-8')
# Users may be using snakeviz in an environment where IPython is not
# installed, this try/except makes sure that snakeviz is operational
# in that case.
try:
    from IPython.core.magic import Magics, magics_class, line_cell_magic
    from IPython.display import display, HTML, IFrame
except ImportError:
    pass
else:

    @magics_class
    class SnakevizMagic(Magics):
        @line_cell_magic
        def snakeviz(self, line, cell=None):
            """
            Profile code and display the profile in Snakeviz.
            Works as a line or cell magic.

            Usage, in line mode:
            %snakeviz [options] statement

            Usage, in cell mode:
            %%snakeviz [options] [statement]
            code...
            code...

            Options:

            -t/--new-tab
            If running the snakeviz magic in the Jupyter Notebook,
            use this flag to open snakeviz visualization in a new tab
            instead of embedded within the notebook.

            Note that this will briefly open a server with host 0.0.0.0,
            which in some situations may present a slight security risk as
            0.0.0.0 means that the server will be available on all network
            interfaces (if they are not blocked by something like a firewall).

            """
            # get location for saved profile
            filename = tempfile.NamedTemporaryFile().name

            # parse options
            opts, line = self.parse_options(line, "tnH:p:f:qe:", "new-tab", posix=False)

            # call signature for prun
            line = "-q -D " + filename + " " + line

            # generate the stats file using IPython's prun magic
            ip = get_ipython()
            if "q" in opts:
                oldq=sys.stdout
                sys.stdout = open(os.devnull, 'w')
            if cell:
                ip.run_cell_magic("prun", line, cell)
            else:
                ip.run_line_magic("prun", line)
            
            if "q" in opts:
                sys.stdout = oldq
            # start up a Snakeviz server
            if _check_ipynb() and not ("t" in opts or "new-tab" in opts):
                if "f" not in opts and "q" not in opts:
                    print("Embedding SnakeViz in this document...")
                sv = open_snakeviz_and_display_in_notebook(filename,opts)
            else:
                print("Opening SnakeViz in a new tab...")
                sv = subprocess.Popen(
                    [sys.executable, "-m", "snakeviz", filename]
                )
            # give time for the Snakeviz page to load then shut down the server
            time.sleep(3)
            if "f" not in opts:
                sv.terminate()


def load_ipython_extension(ipython):
    """Called when user runs %load_ext snakeviz"""
    ipython.register_magics(SnakevizMagic)


def _check_ipynb():
    """
    Returns True if IPython is running as the backend for a
    Jupyter Notebook.

    """
    cfg = get_ipython().config
    return "connection_file" in cfg["IPKernelApp"]


def open_snakeviz_and_display_in_notebook(filename,opts={}):
    def _find_free_port():
        import socket
        from contextlib import closing

        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            # Try a default range of five ports, then use whatever's free.
            ports = list(range(8080, 8085)) + [0]
            for port in ports:
                try:
                    s.bind(("", port))
                except socket.error as e:
                    if e.errno == errno.EADDRINUSE:
                        pass
                    else:
                        raise
                else:
                    return s.getsockname()[1]
                
    if "n" in opts:
        n=opts["n"]
    else:
        n="None"
        
    if "p" in opts:
        port=opts["p"]
    else:
        port = str(_find_free_port())
    
    if "H" in opts:
        H=opts["H"]
    else:
        H="0.0.0.0"
        
    if "f" in opts:
        f=opts["f"]
    else:
        f="None" if n != "None" else tempfile.NamedTemporaryFile().name
        
    if "e" in opts:
        exec=opts["e"]
    else:
        exec=sys.executable
        
    def _start_and_wait_when_ready():
        import os
        #print(f)
        environ = os.environ.copy()
        environ["PYTHONUNBUFFERED"] = "TRUE"
        sv = subprocess.Popen(
            [
                exec,
                "-m",
                "snakeviz_study",
                "-s",
                "-H",
                H,
                "-p",
                port,
                "-f",
                f,
                filename,
            ],
            stdout=subprocess.PIPE,
            universal_newlines=True,
            env=environ,
        )
        if f == "None":
            lines=[]
            o=0
            while True:
                line = sv.stdout.readline()
                if line.strip().startswith("snakeviz web server started"):
                    break
                lines.append(line)
                sleep(2)
                o+=1
                if o==10:
                    print("bugs",lines, [
                sys.executable,
                "-m",
                "snakeviz_study",
                "-s",
                "-H",
                H,
                "-p",
                port,
                "-f",
                f,
                filename,
            ])
                    break
        return sv
    sv = _start_and_wait_when_ready()
    if f == "None":
        path = "/snakeviz/%s" % quote(filename, safe="")
        display(
            HTML(
                JUPYTER_HTML_TEMPLATE.format(
                    port=port, path=path, uuid=uuid.uuid1()
                )
            )
        )
        return sv
    sleep(2)
    display(IFrame(getUrlWithHtml(f),"100%",750))
