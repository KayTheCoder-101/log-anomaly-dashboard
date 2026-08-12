import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loghub_loader import parse_line


class TestParseLine:
    def test_standard_line_with_ip(self):
        line = '199.72.81.55 - - [01/Jul/1995:00:00:01 -0400] "GET /history/apollo/ HTTP/1.0" 200 6245\n'
        result = parse_line(line)
        assert result is not None
        assert result["source_ip"] == "199.72.81.55"
        assert result["endpoint"] == "/history/apollo/"
        assert result["method"] == "GET"
        assert result["status_code"] == 200
        assert result["bytes_sent"] == 6245

    def test_line_with_hostname_instead_of_ip(self):
        # NASA logs mix real IPs and hostnames in the same field — this was
        # a real gotcha flagged during Step 1 (source_ip isn't always an IP).
        line = 'unicomp6.unicomp.net - - [01/Jul/1995:00:00:06 -0400] "GET /shuttle/countdown/ HTTP/1.0" 200 3985\n'
        result = parse_line(line)
        assert result is not None
        assert result["source_ip"] == "unicomp6.unicomp.net"

    def test_dash_bytes_treated_as_zero(self):
        # "-" appears when no content was returned (e.g. 304 Not Modified).
        # Must not crash trying to int("-") — this was a real bug we hit.
        line = 'burger.letters.com - - [01/Jul/1995:00:00:11 -0400] "GET /shuttle/countdown/liftoff.html HTTP/1.0" 304 -\n'
        result = parse_line(line)
        assert result is not None
        assert result["bytes_sent"] == 0
        assert result["status_code"] == 304

    def test_literal_zero_bytes_still_zero(self):
        # Distinct from the "-" case: an explicit "0" should also parse to 0,
        # not be confused with the missing-data sentinel.
        line = 'ppp160.iadfw.net - - [01/Jul/1995:00:18:44 -0400] "GET /htbin/wais.pl HTTP/1.0" 200 0\n'
        result = parse_line(line)
        assert result is not None
        assert result["bytes_sent"] == 0

    def test_response_time_and_user_agent_always_none(self):
        # NASA logs don't have these fields; we must never fabricate values.
        line = '199.72.81.55 - - [01/Jul/1995:00:00:01 -0400] "GET /history/apollo/ HTTP/1.0" 200 6245\n'
        result = parse_line(line)
        assert result["response_time_ms"] is None
        assert result["user_agent"] is None

    def test_endpoint_with_query_string(self):
        # cgi-bin imagemap requests include a query string with no spaces,
        # e.g. "GET /cgi-bin/imagemap/countdown?99,176 HTTP/1.0" — endpoint
        # should capture the full path+query as one token.
        line = '205.189.154.54 - - [01/Jul/1995:00:18:43 -0400] "GET /cgi-bin/imagemap/countdown?99,176 HTTP/1.0" 302 98\n'
        result = parse_line(line)
        assert result is not None
        assert result["endpoint"] == "/cgi-bin/imagemap/countdown?99,176"

    def test_malformed_line_returns_none(self):
        # Not matching the expected combined log format at all.
        line = "this is not a valid log line\n"
        result = parse_line(line)
        assert result is None

    def test_empty_line_returns_none(self):
        result = parse_line("\n")
        assert result is None

    def test_unparseable_timestamp_returns_none(self):
        # Right shape but an invalid/garbage timestamp — must not crash,
        # just skip the line (this is what "Skipped (unparsed)" counts on).
        line = '199.72.81.55 - - [not-a-real-date] "GET /history/apollo/ HTTP/1.0" 200 6245\n'
        result = parse_line(line)
        assert result is None

    def test_status_code_is_int_not_string(self):
        line = '199.72.81.55 - - [01/Jul/1995:00:00:01 -0400] "GET /history/apollo/ HTTP/1.0" 200 6245\n'
        result = parse_line(line)
        assert isinstance(result["status_code"], int)
        assert isinstance(result["bytes_sent"], int)

    def test_timestamp_is_valid_iso_format(self):
        line = '199.72.81.55 - - [01/Jul/1995:00:00:01 -0400] "GET /history/apollo/ HTTP/1.0" 200 6245\n'
        result = parse_line(line)
        from datetime import datetime
        parsed_back = datetime.fromisoformat(result["timestamp"])
        assert parsed_back.year == 1995
        assert parsed_back.month == 7
        assert parsed_back.day == 1
