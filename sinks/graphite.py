"""
Supports flushing metrics to graphite
"""
import sys
import socket
import logging


class GraphiteStore(object):
    def __init__(self, host="localhost", port=2003, prefix="statsite", attempts=3, append=None):
        """
        Implements an interface that allows metrics to be persisted to Graphite.
        Raises a :class:`ValueError` on bad arguments.

        :Parameters:
            - `host` : The hostname of the graphite server.
            - `port` : The port of the graphite server
            - `prefix` (optional) : A prefix to add to the keys. Defaults to 'statsite'
            - `attempts` (optional) : The number of re-connect retries before failing.
            - `append` (optional) : A string to append to the keys with a dash. Disabled by default.
        """
        # Convert the port to an int since its coming from a configuration file
        port = int(port)
        attempts = int(attempts)

        if port <= 0:
            raise ValueError("Port must be positive!")
        if attempts <= 1:
            raise ValueError("Must have at least 1 attempt!")

        self.host = host
        self.port = port
        self.prefix = prefix
        self.attempts = attempts
        self.append = append
        self.sock = self._create_socket()
        self.logger = logging.getLogger("statsite.graphitestore")
        self.hostname = socket.gethostname()

    def flush(self, metrics):
        """
        Flushes the metrics provided to Graphite.

       :Parameters:
        - `metrics` : A list of (key,value,timestamp) tuples.
        """
        if not metrics:
            return

        # Construct the output
        metrics = [m.split("|") for m in metrics if m]
        self.logger.info("Outputting %d metrics" % len(metrics))

        lines = self._build_lines(metrics)  # this was getting too complicated for list comps

        data = "\n".join(lines) + "\n"

        # Serialize writes to the socket
        try:
            self._write_metric(data)
        except:
            self.logger.exception("Failed to write out the metrics!")

    def close(self):
        """
        Closes the connection. The socket will be recreated on the next
        flush.
        """
        self.sock.close()

    def _create_socket(self):
        """Creates a socket and connects to the graphite server"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        return sock

    def _build_lines(self, metrics):
        for k, v, ts in metrics:
            # hack to insert the hostname into the graphite namespace
            namespace = k.split('.')
            namespace.insert(-1, self.hostname)
            k = '.'.join(namespace)
            try:
                if self.prefix and self.append:
                    yield "{0}.{1}-{2} {3} {4}".format(self.prefix, k, self.append, v, ts)
                elif self.prefix:
                    yield "{0}.{1} {2} {3}".format(self.prefix, k, v, ts)
                elif self.append:
                    yield "{0}-{1} {2} {3}".format(k, self.append, v, ts)
                else:
                    yield "{0} {1} {2}".format(k, v, ts)
            except Exception:
                pass

    def _write_metric(self, metric):
        """Tries to write a string to the socket, reconnecting on any errors"""
        for attempt in xrange(self.attempts):
            try:
                self.sock.sendall(metric)
                return
            except socket.error:
                self.logger.exception("Error while flushing to graphite. Reattempting...")
                self.sock = self._create_socket()

        self.logger.critical("Failed to flush to Graphite! Gave up after %d attempts." % self.attempts)


if __name__ == "__main__":
    # Initialize the logger
    logging.basicConfig()

    # Intialize from our arguments
    graphite = GraphiteStore(*sys.argv[1:])

    # Get all the inputs
    metrics = sys.stdin.read()

    # Flush
    graphite.flush(metrics.splitlines())
    graphite.close()
