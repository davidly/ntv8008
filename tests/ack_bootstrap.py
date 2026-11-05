#!/usr/bin/env python3
"""ACK Unix build prerequisites must be checked before building anything."""
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ack_unix_build', ROOT/'ack/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class Prerequisites(unittest.TestCase):
    def test_berkeley_yacc_does_not_replace_bison(self):
        with patch.object(bootstrap, 'find_make', return_value='gmake'), \
             patch.object(bootstrap.shutil, 'which', side_effect=lambda t: None if t=='bison' else '/usr/bin/'+t):
            with self.assertRaisesRegex(SystemExit, 'Missing ACK build tool\\(s\\): bison') as error:
                bootstrap.check_tools()
        self.assertIn('sudo apt install', str(error.exception))

    def test_all_missing_tools_are_reported(self):
        with patch.object(bootstrap, 'find_make', return_value='gmake'), \
             patch.object(bootstrap.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(SystemExit, 'ninja, gcc, flex, yacc, bison'):
                bootstrap.check_tools()

    def test_complete_toolchain_returns_selected_make(self):
        with patch.object(bootstrap, 'find_make', return_value='gmake'), \
             patch.object(bootstrap.shutil, 'which', side_effect=lambda t: '/usr/bin/'+t) as which:
            self.assertEqual(bootstrap.check_tools(), 'gmake')
        self.assertEqual([call.args[0] for call in which.call_args_list],
                         ['ninja','gcc','flex','yacc','bison'])

    def test_failure_precedes_downloads_and_builds(self):
        with patch.object(bootstrap, 'check_tools', side_effect=SystemExit('missing bison')), \
             patch.object(bootstrap, 'unpack') as unpack, \
             patch.object(bootstrap.subprocess, 'run') as run, \
             patch.object(bootstrap, 'BUILD') as build:
            with self.assertRaises(SystemExit):
                bootstrap.main()
        unpack.assert_not_called()
        run.assert_not_called()
        build.mkdir.assert_not_called()


class Downloads(unittest.TestCase):
    def setUp(self):
        # Expected simulated download failures should not look like real ones
        # in the regression runner's output.
        output = redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_connection_reset_and_incomplete_read_are_retried(self):
        from unittest.mock import MagicMock
        response=MagicMock()
        response.__enter__.return_value=response
        response.read.side_effect=[bootstrap.http.client.IncompleteRead(b'partial'),b'complete']
        with patch.object(bootstrap.urllib.request,'urlopen',side_effect=[
                bootstrap.urllib.error.URLError(ConnectionResetError()),response,response]) as fetch, \
             patch.object(bootstrap.time,'sleep') as sleep:
            self.assertEqual(bootstrap.download('https://example.invalid/archive'),b'complete')
        self.assertEqual(fetch.call_count,3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list],[1,2])

    def test_permanent_http_error_is_not_retried(self):
        error=bootstrap.urllib.error.HTTPError('url',404,'not found',{},None)
        with patch.object(bootstrap.urllib.request,'urlopen',side_effect=error) as fetch, \
             patch.object(bootstrap.time,'sleep') as sleep:
            with self.assertRaises(bootstrap.urllib.error.HTTPError):bootstrap.download('url')
        self.assertEqual(fetch.call_count,1)
        sleep.assert_not_called()
        error.close()

    def test_transient_http_errors_have_a_bounded_retry_count(self):
        error=bootstrap.urllib.error.HTTPError('url',503,'unavailable',{},None)
        with patch.object(bootstrap.urllib.request,'urlopen',side_effect=error) as fetch, \
             patch.object(bootstrap.time,'sleep'):
            with self.assertRaises(bootstrap.urllib.error.HTTPError):bootstrap.download('url')
        self.assertEqual(fetch.call_count,3)

    def test_checksum_mismatch_is_not_cached_or_retried(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(bootstrap,'BUILD',Path(directory)), \
             patch.object(bootstrap,'download',return_value=b'wrong archive') as fetch:
            with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
                bootstrap.unpack('lua','url','0'*64,'NTV8008_TEST_MISSING_ARCHIVE')
            self.assertFalse(Path(directory,'lua.tar.gz').exists())
        fetch.assert_called_once_with('url')


if __name__=='__main__':
    unittest.main()
