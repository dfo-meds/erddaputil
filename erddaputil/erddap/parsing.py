"""Incomplete efforts at an ERDDAP log parser. """
import enum
import datetime
from urllib.parse import unquote_plus


class ParserState(enum.Enum):

    NEW = 0
    IN_REQUEST = 1
    IN_STARTUP = 2
    IN_LOAD_DATASETS = 3
    IN_LOAD_DATASETS_REPORT = 4
    DAILY_REPORT = 5
    STATUS_REPORT = 6
    STATUS_REPORT_THREADS = 7
    DAILY_REPORT_EMAIL = 8
    EMAIL = 9


class ErddapRequest:

    def __init__(self,
                 line_no: int,
                 request_no: int,
                 request_time: datetime.datetime,
                 username: str,
                 ip_address: str,
                 request_method: str,
                 request_path: str,
                 result: str,
                 time_ms: int
                 ):
        self.line_no = line_no
        self.request_number = request_no
        self.request_time = request_time
        self.username = username
        self.ip_address = ip_address
        self.request_method = request_method
        self.request_path = request_path
        self.result = result
        self.time_ms = time_ms
        self.extras = {}
        self.other_lines = []


class ErddapLogParser:

    def __init__(self):
        self.state = ParserState.NEW
        self._buffer = []
        self._first_pass_removed = []
        self._blank_count = 0

    def parse(self, file_handle):
        for idx, line in enumerate(file_handle):
            self.parse_line(line.strip("\r\n\t "), idx)
        self.handle_buffer()

    def parse_line(self, line, lineno):

        # Track blank lines in a row
        if not line:
            self._blank_count += 1
        else:
            self._blank_count = 0

        # Start of request info
        if self.state == ParserState.NEW and line.startswith("{{{{"):
            self.handle_buffer()
            self.state = ParserState.IN_REQUEST
            self._buffer.append((lineno, line))

        # End of request info
        elif self.state == ParserState.IN_REQUEST and "}}}}" in line:
            self._buffer.append((lineno, line))
            self.handle_buffer()
            self.state = ParserState.NEW

        elif self.state == ParserState.NEW and line.startswith("==== BEGIN ="):
            self.handle_buffer()
            self.state = ParserState.EMAIL

        elif self.state == ParserState.EMAIL and line.startswith("==== END ="):
            self.handle_buffer()
            self.state = ParserState.NEW

        # Start of dataset loads
        elif self.state == ParserState.NEW and line.startswith("*** RunLoadDatasets"):
            self.handle_buffer()
            self.state = ParserState.IN_LOAD_DATASETS
            self._buffer.append((lineno, line))

        # This indicates we are done the load dataset and just need to pick up a few final report items
        elif self.state == ParserState.IN_LOAD_DATASETS and line.startswith("LoadDatasets.run finished"):
            self.state = ParserState.IN_LOAD_DATASETS_REPORT
            self._buffer.append((lineno, line))

        # Blank line denotes the end of the report items
        elif self.state == ParserState.IN_LOAD_DATASETS_REPORT and line == "":
            self.handle_buffer()
            self.state = ParserState.NEW

        # Start of the Daily Report
        elif self.state == ParserState.NEW and (line == "Daily Report" or line == "Daily Report:"):
            self.handle_buffer()
            self.state = ParserState.DAILY_REPORT
            self._buffer.append((lineno, line))

        # End of the daily report, except there's some emails and debug info that follow
        elif self.state == ParserState.DAILY_REPORT and line == "End of Daily Report":
            self._buffer.append((lineno, line))
            self.state = ParserState.DAILY_REPORT_EMAIL

        # Trailing info for daily report
        elif self.state == ParserState.DAILY_REPORT_EMAIL:

            if line == "" or line.startswith("Email") or line.startswith("*** RunLoadDatasets notes "):
                self._buffer.append((lineno, line))
            else:
                self.handle_buffer()
                self.state = ParserState.NEW
                self.parse_line(line, lineno)

        # Start of the status report output
        elif self.state == ParserState.NEW and line.startswith("Current time is "):
            self.handle_buffer()
            self.state = ParserState.STATUS_REPORT
            self._buffer.append((lineno, line))

        # The last thing in the status report is the thread list
        elif self.state == ParserState.STATUS_REPORT and line.startswith("Number of threads: "):
            self.state = ParserState.STATUS_REPORT_THREADS

        # The thread list is followed by three blank lines
        elif self.state == ParserState.STATUS_REPORT_THREADS and self._blank_count >= 3:
            self.handle_buffer()
            self.state = ParserState.NEW

        # Start of startup block
        elif self.state == ParserState.NEW and line.startswith(r"\\\\****"):
            self.handle_buffer()
            self.state = ParserState.IN_STARTUP
            self._buffer.append((lineno, line))

        # End of startup block
        elif self.state == ParserState.IN_STARTUP and line.startswith(r"\\\\****"):
            self._buffer.append((lineno, line))
            self.handle_buffer()
            self.state = ParserState.NEW

        # Default is just to expand the buffer
        else:
            self._buffer.append((lineno, line))

    def handle_buffer(self):
        # Skip blank lines or those only containing stars
        lines = []
        for line in self._buffer:
            if line[1] == "":
                continue
            if all(x == '*' or x == ' ' for x in line[1]):
                continue
            lines.append(line)
        if not lines:
            return
        # Delegate to handler functions as appropriate
        elif self.state == ParserState.IN_REQUEST:
            self.handle_request_block(lines)
        elif self.state == ParserState.IN_STARTUP:
            self.handle_startup_block(lines)
        elif self.state == ParserState.IN_LOAD_DATASETS:
            self.handle_load_block(lines)
        elif self.state == ParserState.IN_LOAD_DATASETS_REPORT:
            self.handle_load_report_block(lines)
        elif self.state == ParserState.DAILY_REPORT_EMAIL:
            self.handle_daily_report(lines)
        elif self.state == ParserState.STATUS_REPORT_THREADS:
            self.handle_status_report(lines)
        elif self.state == ParserState.EMAIL:
            self.handle_email(lines)
        else:
            self.handle_unknown_section(lines)
        self._buffer = []

    def handle_email(self, lines):
        #print(">email<")
        pass

    def handle_unknown_section(self, lines):
        #print(">unknown<")
        #for num, x in self._buffer:
        #    print(f"{num}: {x} [{len(x)}]")
        pass

    def handle_status_report(self, lines):
        #print(">status report<")
        pass

    def handle_daily_report(self, lines):
        #print(">daily report<")
        #for idx, x in lines:
        #    print(f"{idx}: {x}")
        pass

    def handle_startup_block(self, lines):
        #print(">startup report<")
        pass

    def handle_request_block(self, lines):
        first_info = lines[0][1][4:].split(" ")
        last_info = lines[-1][1][4:].split(" ")
        request = ErddapRequest(
            lines[0][0],
            int(first_info[0][1:]),
            datetime.datetime.fromisoformat(first_info[1]),
            first_info[2] if first_info[2] != '(notLoggedIn)' else None,
            first_info[3] if first_info[3] != '(unknownIPAddress)' else None,
            first_info[4],
            first_info[5],
            last_info[2].strip("."),
            int(last_info[3][5:-2])
        )
        for i in range(1, len(lines) - 1):
            line = lines[i][1]
            if line.startswith("OutputStreamFromHttpResponse"):
                pieces = [x.strip(", ") for x in line.split(" ") if x.strip(", ")]
                request.extras["handler"] = pieces[0]
                for piece in pieces:
                    if "=" in piece:
                        k, v= piece.split("=", maxsplit=1)
                        request.extras[k] = v
                request.extras["extension"] = pieces[-1]
            elif line.startswith("redirected to"):
                request.extras["redirect"] = line[14:]
            elif line.startswith("doTransfer"):
                request.extras["source_file"] = line[11:]
            elif line.startswith("compression="):
                pieces = [x.strip(", ") for x in line.split(" ") if x.strip(", ")]
                for piece in pieces:
                    if "=" in piece:
                        k, v = piece.split("=", maxsplit=1)
                        request.extras[k] = v
            elif line.startswith("graphQuery="):
                qs = line[11:]
                graph_query = {
                }
                for kv in qs.split("&"):
                    if "=" in kv:
                        k, v = kv.split("=", maxsplit=1)
                        graph_query[unquote_plus(k)] = unquote_plus(v)
                    else:
                        graph_query[unquote_plus(kv)] = ''
                request.extras['graph_query'] = graph_query
            elif line.startswith('}} SgtMap.makeMap done'):
                request.extras['map_time_ms'] = int(line[line.find("=")+1:-2])
            elif line.startswith("SgtUtil.saveAsPng"):
                request.extras["png_time_ms"] = int(line[line.find("=")+1:-2])
            elif line == "writePngInfo succeeded":
                pass
            else:
                request.other_lines.append(line[1])
        self.erddap_request(request)

    def erddap_request(self, request):
        self.default_handler(request)

    def handle_load_block(self, lines):
        #print(">dataset load<")
        pass

    def handle_load_report_block(self, lines):
        #print(">dataset load report<")
        pass

    def default_handler(self, obj):
        pass
