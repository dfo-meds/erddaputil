"""ERDDAP parsing """
import enum
from urllib.parse import unquote_plus
from bs4 import BeautifulSoup
import typing as t
import re
import datetime
from urllib.parse import unquote
import zrlog

COMMON_FORMAT = "%h %l %u %t \"%r\" %s %b"
COMBINED_FORMAT = "%h %l %u %t \"%r\" %s %b \"%{Referer}\" \"%{User-Agent}\""


class TomcatLog:

    def __init__(self, mapping: dict, tomcat_major_version: int = 10):
        self._tomcat_version = tomcat_major_version
        self._mapping = mapping

    def __str__(self):
        return '\n'.join(f'{key}: {self._mapping[key]}' for key in self._mapping)

    def value(self, flag, default=None, hyphen_to_default: bool = False, blank_to_default: bool = True, coerce = None):
        if flag not in self._mapping:
            return default
        if hyphen_to_default and self._mapping[flag] == "-":
            return default
        if flag in self._mapping and self._mapping[flag] is None or self._mapping[flag] == "":
            return default
        return self._mapping[flag] if coerce is None else coerce(self._mapping[flag])

    def ivalue(self, flag, default=None, hyphen_to_default: bool = False, blank_to_default: bool = True, coerce = None):
        for n in self._mapping:
            if flag.lower() == n.lower():
                return self.value(n, default, hyphen_to_default, blank_to_default, coerce)
        return default

    def bytes_sent(self):
        bytes = self.value('%b', hyphen_to_default=True, coerce=int)
        if bytes is None:
            bytes = self.value('%B', coerce=int)
        return bytes

    def remote_ip(self):
        return self.value('%a')

    def local_ip(self):
        return self.value('%A')

    def remote_host(self):
        return self.value('%h')

    def request_protocol(self):
        return self.value('%H')

    def thread_name(self):
        return self.value('%I')

    def http_version(self):
        _, _, version = self._parse_request_line()
        return version

    def _parse_request_line(self) -> tuple[str, str, str]:
        v = self.request()
        if v.count(' ') == 2:
            return v.split(' ', maxsplit=2)
        else:
            return None, None, None

    def extension(self):
        uri = self.request_uri()[8:]
        if '/' not in uri:
            return None
        last_piece = uri[uri.rfind('/')+1:]
        if '.' in last_piece:
            return last_piece[last_piece.rfind('.')+1:].lower()
        return None

    def request_method(self):
        method = self.value('%m')
        if method is None:
            method, _, _ = self._parse_request_line()
        return method

    def request_port(self):
        return self.value('%p')

    def request_query(self):
        val = self.value('%q')
        if val is None:
            _, val, _ = self._parse_request_line()
            if val and '?' in val:
                val = val[val.find('?'):]
            else:
                val = ""
        return val

    def parsed_query(self):
        query = self.request_query()
        if not query:
            return {}
        query_parameters = {}
        pieces = query[1:].split('&')
        for piece in pieces:
            if '=' in piece:
                key, val = piece.split('=', maxsplit=1)
            else:
                key, val = piece, None
            if key in query_parameters:
                if not isinstance(query_parameters, list):
                    query_parameters[key] = list[query_parameters[key]]
                query_parameters[key].append(val)
            else:
                query_parameters[key] = val
        return query_parameters

    def request(self):
        return self.value('%r')

    def status_code(self):
        s = self.value('%s')
        if s is None:
            return self.value('%>s')
        else:
            return s

    def session_id(self):
        return self.value('%S')

    def request_time(self):
        dt = self.value('%t')
        return datetime.datetime.strptime(dt, '%d/%b/%y:%H:%M:%S %z') if dt else None

    def request_processing_time_ms(self):
        d_flag = self.value('%D', coerce=float)
        if d_flag is not None:
            return d_flag if self._tomcat_version < 10 else (d_flag / 1000)
        else:
            t_flag = self.value('%T', coerce=float)
            if t_flag is not None:
                return t_flag if self._tomcat_version < 10 else (t_flag * 1000)
            return None

    def request_commit_time_ms(self):
        return self.value('%F')

    def remote_user(self):
        return self.value('%u')

    def request_uri(self):
        val = self.value('%U')
        if val is None:
            _, val, _ = self._parse_request_line()
            if val and '?' in val:
                val = val[0:val.find('?')]
        return val

    def server_name(self):
        return self.value('%v')

    def connection_status(self):
        return self.value('%X')

    def header_received(self, header_name: str):
        return self.ivalue(f'%{header_name.lower()}i')

    def header_sent(self, header_name: str):
        return self.ivalue(f'%{header_name.lower()}o')

    def cookie_sent(self, cookie_name: str):
        return self.ivalue(f'%{cookie_name.lower()}c')

    def placeholders(self) -> dict:
        pt = self.request_processing_time_ms()
        return {
            '%a': self.remote_ip() or "-",
            '%b': self.bytes_sent() or '-',
            '%U': self.request_uri() or "-",
            '%T': (pt / 1000.0) if pt is not None else "-",
            '%s': self.status_code() or "-",
            '%r': self.request() or "-",
            '%q': self.request_query() or "-",
            '%m': self.request_method() or "-",
            '%h': self.remote_host() or "-",
        }


class TomcatLogParser:

    RAW_SLASH = f'{chr(26)}{chr(17)}'
    RAW_QUOTE = f'{chr(26)}{chr(18)}'

    def __init__(self, log_formats=None, tomcat_major_version: int = 10, encoding="utf-8"):
        self._tomcat_version = tomcat_major_version
        self._encoding = encoding
        self.log_formats = []
        self.log = zrlog.get_logger("erddaputil.erddap.parsing.tomcat")
        if log_formats is None:
            self.log_formats = [COMMON_FORMAT]
        elif isinstance(log_formats, str):
            if log_formats == 'common':
                self.log_formats = [COMMON_FORMAT]
            elif log_formats == 'combined':
                self.log_formats = [COMBINED_FORMAT]
            else:
                self.log_formats = [log_formats]
        else:
            for lf in log_formats:
                if lf == 'common':
                    self.log_formats.append(COMMON_FORMAT)
                elif lf == 'combined':
                    self.log_formats.append(COMBINED_FORMAT)
                else:
                    self.log_formats.append(lf)
        self.regex_options = [
            self._build_regex(lf) for lf in self.log_formats
        ]

    def _build_regex(self, lf: str):
        pieces = lf.split(" ")
        regex_pieces = []
        for piece in lf.split(" "):
            if not piece:
                regex_pieces.append((' ', {'raw': True}))
            if '%' not in piece:
                regex_pieces.append((piece, {'raw': True}))
            elif piece == '%t':
                regex_pieces.append((piece, {'escape': ']', 'prefix': '[', 'suffix': ']', 'raw': False}))
            elif piece[0] == '"' and piece[-1] == '"':
                regex_pieces.append((piece[1:-1], {'escape': '"', 'prefix': '"', 'suffix': '"', 'raw': False}))
            elif piece[0] == "'" and piece[-1] == "'":
                regex_pieces.append((piece[1:-1], {'escape': "'", 'prefix': "'", 'suffix': "'", 'raw': False}))
            else:
                regex_pieces.append((piece, {'escape': ' ', 'raw': False, 'prefix': '', 'suffix': ''}))
        regex = re.compile(' '.join(self._build_regex_piece(*x) for x in regex_pieces))
        groups = [r[0] for r in regex_pieces if not r[1]['raw']]
        self.log.debug(f"Tomcat log regex loaded [{regex.pattern}]")
        return regex, groups

    def _build_regex_piece(self, piece, options):
        if options['raw']:
            return re.escape(piece)
        else:
            return re.escape(options['prefix']) + '([^' + re.escape(options['escape']) + ']*)' + re.escape(options['suffix'])

    def parse_line(self, line):
        line = line.replace('\\\\', self.RAW_SLASH).replace('\\"', self.RAW_QUOTE)
        for regex, groups in self.regex_options:
            match = regex.match(line)
            if not match:
                continue
            values = [
                x.replace(self.RAW_SLASH, '\\').replace(self.RAW_QUOTE, '"')
                for x in match.groups()
            ]
            return TomcatLog(dict(zip(groups, values)), self._tomcat_version)
        else:
            self.log.warning(f"Line not parseable: {line}")

    def parse(self, content):
        if isinstance(content, bytes):
            content = content.decode(self._encoding)
        for line in content.split("\n"):
            if line:
                res = self.parse_line(line)
                if res:
                    yield res


class DapQuery:

    def __init__(self, variables, constraints, grid_bounds):
        self.variables = variables
        self.constraints = constraints
        self.grid_bounds = grid_bounds

    def __str__(self):
        sep = '\n  '
        return f"""variables: 
  {sep.join(self.variables)}
constraints: 
  {sep.join(self.constraints)}
grid_bounds: 
  {sep.join(self.grid_bounds)}
"""

    @staticmethod
    def parse_dap_query(log: TomcatLog):
        query = log.request_query()
        if not query:
            return [], []
        query = query[1:]
        dimensions = ""
        if '&' in query:
            projection = DapQuery._parse_dap_projection(query[:query.find('&')])
            constraints = [DapQuery._parse_dap_constraint(c) for c in query[query.find('&')+1:].split('&')]
        else:
            projection = DapQuery._parse_dap_projection(query)
            constraints = []
        if projection and projection[0] and '[' in projection[0]:
            _projection = []
            for x in projection:
                dimensions = x[x.find('['):]
                _projection.append(x[:x.find('[')])
            projection = _projection
            dimensions = [x.strip('[]') for x in dimensions.split('][')]
        return DapQuery(projection, constraints, dimensions)

    @staticmethod
    def _parse_dap_constraint(constraint):
        constraint = unquote(constraint)
        return constraint

    @staticmethod
    def _parse_dap_projection(projection):
        projection = unquote(projection)
        return projection.split(',')

    def placeholders(self):
        return {
            '%(dap_variables)s': ';'.join(self.variables) if self.variables else '-',
            '%(dap_constraints)s': '&'.join(self.constraints) if self.constraints else '-',
            '%(dap_grid_bounds)s': ';'.join(self.grid_bounds) if self.grid_bounds else '-'
        }

    @staticmethod
    def empty_placeholders():
        return {
            '%(dap_variables)s': '-',
            '%(dap_constraints)s': '-',
            '%(dap_grid_bounds)s': '-'
        }


class ErddapAccessLogEntry:

    def __init__(self, tomcat_log: TomcatLog, dataset_id: str = None, request_type: str = 'web', dap_query: DapQuery = None):
        self.dataset_id = dataset_id
        self.tomcat_log = tomcat_log
        self.request_type = request_type
        self.dap_query = dap_query

    def placeholders(self) -> dict:
        base = {
            '%(request_type)s': self.request_type,
            '%(dataset_id)s': self.dataset_id or "-"
        }
        base.update(self.tomcat_log.placeholders())
        if self.dap_query:
            base.update(self.dap_query.placeholders())
        else:
            base.update(DapQuery.empty_placeholders())
        return base


class ErddapLogParser(TomcatLogParser):

    HTML_PAGES = ['html', 'graph', 'help', 'subset']
    METADATA_PAGES = ['das', 'dds', 'fgdc', 'iso19115', 'ncHeader', 'ncml', 'nccsvMetadata', 'timeGaps', 'ncCFHeader', 'ncCFMAHeader']

    def parse_chunks(self, handle, chunk_size: int = 102400, flag = None):
        chunk = ''
        more = True
        while more:
            more = False
            new = handle.read(chunk_size)
            if new:
                more = True
                chunk += new
                if '\n' in chunk:
                    pos = chunk.rfind("\n")
                    current_chunk = chunk[:pos]
                    chunk = chunk[pos+1:]
                    for log in self.parse(current_chunk):
                        yield log
            if flag and flag.is_set():
                break
        if chunk:
            handle.seek(-1 * len(chunk), 1)

    def parse(self, content):
        for log in super().parse(content):

            # This has NO query string
            uri = log.request_uri()

            # Parse out the dataset_id
            dataset_id = None
            if '/tabledap/' in uri:
                dataset_id = self._extract_dataset_name(uri[uri.find('/tabledap/')+10:])
            elif '/griddap/' in uri:
                dataset_id = self._extract_dataset_name(uri[uri.find('/griddap/') + 9:])

            # These are actually requests for documentation on griddap or table dap
            if dataset_id == 'documentation':
                dataset_id = None

            # Identify the request type
            request_type = 'web'
            if dataset_id is not None:
                request_type = 'data'
                ext = log.extension()
                if ext in ErddapLogParser.HTML_PAGES:
                    request_type = 'web'
                elif ext in ErddapLogParser.METADATA_PAGES:
                    request_type = 'metadata'

            # Build DAP query if applicable
            dap = None
            if request_type == 'data':
                dap = DapQuery.parse_dap_query(log)

            yield ErddapAccessLogEntry(log, dataset_id, request_type, dap)

    def _extract_dataset_name(self, path_suffix):
        if '/' in path_suffix:
            path_suffix = path_suffix[:path_suffix.find('/')]
        if '.' in path_suffix:
            path_suffix = path_suffix[:path_suffix.find('.')]
        return path_suffix


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
    """Holds ERDDAP request info"""

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


class _ErddapInternalLogParser:
    """Parser for log.txt"""

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
                        k, v = piece.split("=", maxsplit=1)
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


class StatusState(enum.Enum):
    """State of ErddapStatusParser"""

    MAIN_BLOCK = 0
    DATASET_FAIL_LIST = 1
    LOAD_DATASET_TIME_SERIES = 2
    LOAD_DISTRIBUTION = 3
    LOAD_LANGUAGE_DISTRIBUTION = 4
    LOAD_THREAD_INFO = 5
    LOAD_MAP_SIZES = 6


class ErddapStatusParser:
    """Parser for status.html content"""

    def __init__(self):
        self.info = {}
        self.state = StatusState.MAIN_BLOCK
        self.not_handled = []
        self.skipped = 0
        self._info_key = None

    def parse(self, content):
        soup = BeautifulSoup(content, "html.parser")
        txt = soup.find("pre").text.split("\n")
        line_no = 1
        for line in txt:
            line = line.strip("\r\n\t")
            if self.state == StatusState.MAIN_BLOCK:
                self._parse_main_block(line, line_no)
            elif self.state == StatusState.DATASET_FAIL_LIST:
                self._parse_ds_fail_block(line, line_no)
            elif self.state == StatusState.LOAD_DATASET_TIME_SERIES:
                self._parse_ds_load_time_series(line, line_no)
            elif self.state == StatusState.LOAD_DISTRIBUTION:
                self._parse_distribution_series(line, line_no)
            elif self.state == StatusState.LOAD_LANGUAGE_DISTRIBUTION:
                self._parse_lang_distribution_series(line, line_no)
            elif self.state == StatusState.LOAD_MAP_SIZES:
                self._parse_map_sizes(line, line_no)
            elif self.state == StatusState.LOAD_THREAD_INFO:
                self._parse_thread_info(line, line_no)
            line_no += 1

    def _parse_map_sizes(self, line, line_no):
        cline = line.strip()
        if "=" in cline:
            cline = cline[:cline.find("=")]
            self.state = StatusState.MAIN_BLOCK
        if cline:
            if self._info_key not in self.info:
                self.info[self._info_key] = []
            self.info[self._info_key].extend([int(x.strip()) for x in cline.split("+") if x.strip()])

    def _parse_thread_info(self, line, line_no):
        cline = line.strip()
        if not cline:
            return
        if "threads" not in self.info:
            self.info["threads"] = {}
        if line.startswith("#"):
            pieces = line.split(" ")
            self._info_key = pieces[0]
            self.info["threads"][self._info_key] = {
                "running_cls": pieces[1],
                "state": pieces[2],
                "type": pieces[3] if len(pieces) > 3 else "?",
                "stack": []
            }
        else:
            self.info["threads"][self._info_key]["stack"].append(line)

    def _parse_lang_distribution_series(self, line, line_no):
        cline = line.strip()
        if not cline:
            self.state = StatusState.MAIN_BLOCK
        elif ":" in cline:
            lang_piece, count_piece = [x.strip() for x in cline.split(":", maxsplit=1)]
            count_piece = count_piece[:count_piece.find("(")].strip()
            lang_piece = lang_piece or "_default_en"
            if self._info_key not in self.info:
                self.info[self._info_key] = {}
            self.info[self._info_key][lang_piece] = int(count_piece)

    def _parse_distribution_series(self, line, line_no):
        cline = line.strip()
        if not cline:
            self.state = StatusState.MAIN_BLOCK
        elif cline.startswith("n ="):
            if "," in cline:
                n_piece, med_piece = cline.split(",")
                med_piece = med_piece[med_piece.find("=")+1:].strip()
                units = ""
                while not med_piece[-1].isdigit():
                    units = med_piece[-1] + units
                    med_piece = med_piece[:-1]
                n_piece = n_piece[n_piece.find("=")+1:].strip()
                self.info[self._info_key] = [int(n_piece), int(med_piece), units.strip(), {}]
            else:
                n_piece = cline[cline.find("=")+1:].strip()
                self.info[self._info_key] = [int(n_piece), None, {}]
                self.state = StatusState.MAIN_BLOCK
        elif cline.startswith(">"):
            _bin, count = [x.strip() for x in cline.split(":")]
            self.info[self._info_key][3][_bin] = int(count)
            self.state = StatusState.MAIN_BLOCK
        elif ":" in cline:
            _bin, count = [x.strip() for x in cline.split(":")]
            self.info[self._info_key][3][_bin] = int(count)

    def _parse_ds_load_time_series(self, line, line_no):
        cline = line.strip(" ")
        if cline.startswith("timestamp"):
            self.info["major_load_time_series"] = []
            pass
        elif cline.startswith("-----"):
            pass
        elif not cline:
            self.state = StatusState.MAIN_BLOCK
        else:
            data = [x.strip("()") for x in cline.split(" ") if x.strip("()")]
            self.info["major_load_time_series"].append(data)

    def _parse_ds_fail_block(self, line, line_no):
        if self._info_key not in self.info:
            self.info[self._info_key] = set()
        if "(end)" in line:
            self.state = StatusState.MAIN_BLOCK
            line = line[:line.find("(end)")]
        if line.strip():
            self.info[self._info_key].update(x.strip() for x in line.strip().split(",") if x.strip())

    def has_info(self, key):
        return key in self.info and self.info[key] is not None and self.info[key] != ""

    def _parse_main_block(self, line, line_no):
        cline = line.strip(" ")
        if cline.startswith("Current time is "):
            self.info["current_time"] = cline[-25:]
        elif cline.startswith("Startup was at "):
            self.info["startup_time"] = cline[-25:]
        elif cline.startswith("Last major LoadDatasets started"):
            p1 = cline.find("started") + 7
            p2 = cline.find("ago")
            self.info["last_major_load_time"] = cline[p1:p2].strip()
            if "after" in cline:
                p3 = cline.find("after") + 5
                self.info["last_major_load_duration"] = cline[p3:].strip(". \r\n\t")
            else:
                self.info["last_major_load_duration"] = None
        elif line.startswith("nGridDatasets"):
            self.info["griddap_count"] = int(line[line.find("=")+1:].strip())
        elif line.startswith("nTableDatasets"):
            self.info["tabledap_count"] = int(line[line.find("=")+1:].strip())
        elif line.startswith("nTotalDatasets"):
            self.info["dataset_count"] = int(line[line.find("=")+1:].strip())

        elif line.startswith("n Datasets Failed To Load"):
            self.info["failed_dataset_count"] = int(line[line.find("=")+1:].strip())
            if self.info["failed_dataset_count"] > 0:
                self.state = StatusState.DATASET_FAIL_LIST
                self._info_key = "failed_datasets"

        elif line.startswith("ERROR: n Orphan Datasets"):
            self.info["orphan_dataset_count"] = int(line[line.find("=") + 1:].strip())
            if self.info["orphan_dataset_count"] > 0:
                self.state = StatusState.DATASET_FAIL_LIST
                self._info_key = "orphan_datasets"

        elif line.startswith("Unique users "):
            self.info["unique_users"] = int(line[line.find("=")+1:].strip())

        elif line.startswith("Response Failed    Time (since last major"):
            self.info["response_failed_since_major_load"] = self._extract_n_median(cline)
        elif line.startswith("Response Failed    Time (since last Daily"):
            self.info["response_failed_since_last_daily"] = self._extract_n_median(cline)
        elif line.startswith("Response Failed    Time (since startup"):
            self.info["response_failed_since_startup"] = self._extract_n_median(cline)

        elif line.startswith("Response Succeeded Time (since last major"):
            self.info["response_success_since_major_load"] = self._extract_n_median(cline)
        elif line.startswith("Response Succeeded Time (since last Daily"):
            self.info["response_success_since_last_daily"] = self._extract_n_median(cline)
        elif line.startswith("Response Succeeded Time (since startup"):
            self.info["response_success_since_startup"] = self._extract_n_median(cline)

        elif line.startswith("TaskThread has finished "):
            self.info["task_count"] = self._extract_count(cline)
        elif line.startswith("TaskThread Failed    Time (since last Daily"):
            self.info["task_failed_since_last_daily"] = self._extract_n_median(cline)
        elif line.startswith("TaskThread Failed    Time (since startup"):
            self.info["task_failed_since_startup"] = self._extract_n_median(cline)

        elif line.startswith("TaskThread Succeeded Time (since last Daily"):
            self.info["task_success_since_last_daily"] = self._extract_n_median(cline)
        elif line.startswith("TaskThread Succeeded Time (since startup"):
            self.info["task_success_since_startup"] = self._extract_n_median(cline)

        elif line.startswith("EmailThread has sent "):
            self.info["email_count"] = self._extract_count(cline)
        elif line.startswith("EmailThread Failed    Time (since last Daily"):
            self.info["email_failed_since_last_daily"] = self._extract_n_median(cline)
        elif line.startswith("EmailThread Succeeded Time (since last Daily "):
            self.info["email_success_since_last_daily"] = self._extract_n_median(cline)

        elif line.startswith("TouchThread has finished "):
            self.info["touch_count"] = self._extract_count(cline)
        elif line.startswith("TouchThread Failed    Time (since last Daily"):
            self.info["touch_failed_since_last_daily"] = self._extract_n_median(cline)
        elif line.startswith("TouchThread Succeeded Time (since last Daily"):
            self.info["touch_success_since_last_daily"] = self._extract_n_median(cline)

        elif line.startswith("OS info:"):
            self.info["os_info"] = self._extract_key_value_dict(cline[8:].strip())

        elif line.startswith("Number of active requests"):
            self.info["active_requests"] = int(cline[cline.find("=")+1:])

        elif line.startswith("Number of threads:"):
            self.info["thread_info"] = self._extract_key_value_dict(cline[18:].strip(), sep=", ")

        elif " gc calls" in line:
            pieces = line.split(" ")
            self.info["gc_calls_since_last_major"] = int(pieces[0])
            self.info["requests_shed_since_last_major"] = int(pieces[3])
            self.info["dangerous_memory_emails_since_last_major"] = int(pieces[7])

        elif line.startswith("MemoryInUse="):
            pieces = [x.strip() for x in line.split(" ") if x.strip()]
            self.info["memory_in_use_mb"] = int(pieces[1])
            self.info["memory_highwater_mark_mb"] = int(pieces[4])
            self.info["memory_xmax_mb"] = int(pieces[8])

        elif line.startswith("Major LoadDatasets Time Series:"):
            self.state = StatusState.LOAD_DATASET_TIME_SERIES

        elif line.startswith("Major LoadDatasets Times Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "major_load_distribution_since_last_daily"

        elif line.startswith("Major LoadDatasets Times Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "major_load_distribution_since_startup"

        elif line.startswith("Minor LoadDatasets Times Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "minor_load_distribution_since_last_daily"

        elif line.startswith("Minor LoadDatasets Times Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "minor_load_distribution_since_startup"

        elif line.startswith("Response Failed Time Distribution (since last major"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "response_failed_distribution_since_last_major"

        elif line.startswith("Response Failed Time Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "response_failed_distribution_since_last_daily"

        elif line.startswith("Response Failed Time Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "response_failed_distribution_since_startup"

        elif line.startswith("Response Succeeded Time Distribution (since last major"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "response_success_distribution_since_last_major"

        elif line.startswith("Response Succeeded Time Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "response_success_distribution_since_last_daily"

        elif line.startswith("Response Succeeded Time Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "response_success_distirbution_since_startup"

        elif line.startswith("EmailThread Failed Time Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "email_failed_distribution_since_last_daily"

        elif line.startswith("EmailThread Failed Time Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "email_failed_distribution_since_startup"

        elif line.startswith("EmailThread Succeeded Time Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "email_success_distribution_since_last_daily"

        elif line.startswith("EmailThread Succeeded Time Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "email_success_distribution_since_startup"

        elif line.startswith("EmailThread nEmails/Session Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "email_count_per_session_distribution_since_last_daily"

        elif line.startswith("EmailThread nEmails/Session Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "email_count_per_session_distribution_since_startup"

        elif line.startswith("TaskThread Failed Time Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "task_failed_distribution_since_last_daily"

        elif line.startswith("TaskThread Failed Time Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "task_failed_distribution_since_startup"

        elif line.startswith("TaskThread Succeeded Time Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "task_success_distribution_since_last_daily"

        elif line.startswith("TaskThread Succeeded Time Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "task_success_distribution_since_startup"

        elif line.startswith("TouchThread Failed Time Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "touch_failed_distribution_since_last_daily"

        elif line.startswith("TouchThread Failed Time Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "touch_failed_distribution_since_startup"

        elif line.startswith("TouchThread Succeeded Time Distribution (since last Daily"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "touch_success_distribution_since_last_daily"

        elif line.startswith("TouchThread Succeeded Time Distribution (since startup"):
            self.state = StatusState.LOAD_DISTRIBUTION
            self._info_key = "touch_success_distribution_since_startup"

        elif line.startswith("Language (since last daily report"):
            self.state = StatusState.LOAD_LANGUAGE_DISTRIBUTION
            self._info_key = "languages_since_last_daily"

        elif line.startswith("Language (since startup"):
            self.state = StatusState.LOAD_LANGUAGE_DISTRIBUTION
            self._info_key = "languages_since_startup"

        elif line.startswith ("SgtMap topography "):
            self.info["sgtmap_info"] = self._extract_key_value_dict(line[17:].strip())

        elif line.startswith("(format: #threadNumber"):
            self.state = StatusState.LOAD_THREAD_INFO

        elif line.startswith("GSHHS:"):
            self.info["gshhs_info"] = self._extract_cached_info(line[6:])

        elif line.startswith("NationalBoundaries:"):
            self.info["nat_bound_info"] = self._extract_cached_info(line[19:])

        elif line.startswith("StateBoundaries:"):
            self.info["state_bound_info"] = self._extract_cached_info(line[16:])

        elif line.startswith("Rivers:"):
            self.info["rivers_info"] = self._extract_cached_info(line[7:])

        elif line.startswith("canonical map sizes:"):
            self.state = StatusState.LOAD_MAP_SIZES
            self._info_key = "canon_map_sizes"
            self._parse_map_sizes(line[20:].strip(), line_no)

        elif line.startswith("canonicalStringHolder map sizes:"):
            self.state = StatusState.LOAD_MAP_SIZES
            self._info_key = "canon_str_holder_map_sizes"
            self._parse_map_sizes(line[32:].strip(), line_no)

        else:
            if cline:
                self.not_handled.append((line, line_no))

    def _extract_cached_info(self, line):
        info = {}
        for piece in [x.strip() for x in line.split(",") if x.strip()]:
            k, v = [x.strip() for x in piece.split("=") if x.strip()]
            if " of " in v:
                p = v.find(" of ")
                info[k] = v[0:p]
                info[k + "_max"] = v[p+4:]
            else:
                info[k] = v
        return info

    def _extract_key_value_dict(self, line, sep=" ", kv_sep="=") -> dict:
        os_info = {}
        for item in line.split(sep):
            k, v = item.split(kv_sep)
            os_info[k] = v
        return os_info

    def _extract_count(self, line) -> tuple[int, int, str]:
        p = line.find(" out of ")
        start = line[0:p].rfind(" ")
        end = line.find(" ", p + 8)
        running_since = None
        if "has been running for" in line:
            p = line.rfind(" for ") + 4
            running_since = line[p:].strip(" \r\n\t.")
        return int(line[start:p].strip()), int(line[p+8:end].strip()), running_since

    def _extract_n_median(self, line) -> tuple[int, t.Optional[int]]:
        n_piece = ""
        median_piece = None
        if line.count("=") == 2:
            _, n_piece, median_piece = line.split("=")
            median_piece = median_piece[:-2].strip()
            n_piece = n_piece[:n_piece.find(",")].strip(" ,")
        else:
            _, n_piece = line.split("=")
            n_piece = n_piece.strip()
        return int(n_piece), int(median_piece) if median_piece is not None else None
