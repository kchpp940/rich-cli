"""Unit tests for win_vt.py Windows virtual terminal processing."""

import sys
from unittest import mock

import pytest


class _MockHandle:
    """Mock Windows HANDLE with .value attribute."""
    def __init__(self, value):
        self.value = value


class _MockDWORD:
    """Mock Windows DWORD with .value attribute."""
    def __init__(self, value=0):
        self.value = value


def _mock_byref(obj):
    """Mock ctypes.byref that returns the object itself for testing."""
    return obj


def _setup_windows_environment():
    """Set up mocks to simulate running on Windows, returns module and mocks."""
    mocks = {}

    mocks["platform_system"] = mock.patch("platform.system", return_value="Windows")
    mocks["platform_system"].start()

    if "rich_cli.win_vt" in sys.modules:
        del sys.modules["rich_cli.win_vt"]

    import ctypes
    import ctypes.wintypes

    kernel32 = mock.MagicMock()
    mocks["kernel32"] = kernel32

    class _Kernel32Wrapper:
        def __init__(self, k32):
            self._k32 = k32

        def __getattr__(self, name):
            return getattr(self._k32, name)

        def __setattr__(self, name, value):
            if name == "_k32":
                object.__setattr__(self, name, value)
            else:
                pass

    original_windll = getattr(ctypes, "WinDLL", None)
    ctypes.WinDLL = mock.Mock(return_value=_Kernel32Wrapper(kernel32))

    original_handle = getattr(ctypes.wintypes, "HANDLE", None)
    ctypes.wintypes.HANDLE = _MockHandle

    original_dword = getattr(ctypes.wintypes, "DWORD", None)
    ctypes.wintypes.DWORD = _MockDWORD

    original_pointer = getattr(ctypes, "POINTER", None)
    ctypes.POINTER = mock.Mock(return_value=mock.Mock())

    mocks["cleanup"] = (original_windll, original_handle, original_dword, original_pointer)

    import rich_cli.win_vt as win_vt_module

    mocks["byref_patch"] = mock.patch.object(win_vt_module, "byref", _mock_byref)
    mocks["byref_patch"].start()

    return win_vt_module, mocks


def _teardown_windows_environment(mocks):
    """Clean up mocks and restore original state."""
    import ctypes
    import ctypes.wintypes

    mocks["byref_patch"].stop()

    original_windll, original_handle, original_dword, original_pointer = mocks["cleanup"]
    if original_windll is not None:
        ctypes.WinDLL = original_windll
    else:
        try:
            del ctypes.WinDLL
        except AttributeError:
            pass

    if original_handle is not None:
        ctypes.wintypes.HANDLE = original_handle
    else:
        try:
            del ctypes.wintypes.HANDLE
        except AttributeError:
            pass

    if original_dword is not None:
        ctypes.wintypes.DWORD = original_dword
    else:
        try:
            del ctypes.wintypes.DWORD
        except AttributeError:
            pass

    if original_pointer is not None:
        ctypes.POINTER = original_pointer
    else:
        try:
            del ctypes.POINTER
        except AttributeError:
            pass

    mocks["platform_system"].stop()

    if "rich_cli.win_vt" in sys.modules:
        del sys.modules["rich_cli.win_vt"]


class TestWindowsConsoleVTClass:
    """Test the WindowsConsoleVT state class directly."""

    def test_state_encapsulation_invalid_handle(self):
        """Test state remains clean when GetStdHandle fails."""
        win_vt, mocks = _setup_windows_environment()
        try:
            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(-1)

            vt = win_vt.WindowsConsoleVT()
            assert vt._handle is None
            assert vt.original_mode is None
            assert vt.enabled_by_context is False

            with vt:
                assert vt._handle is not None
                assert vt.original_mode is None
                assert vt.enabled_by_context is False

            assert vt.enabled_by_context is False
            assert vt.original_mode is None
            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)

    def test_state_encapsulation_console_mode_fail(self):
        """Test state remains clean when GetConsoleMode fails."""
        win_vt, mocks = _setup_windows_environment()
        try:
            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)
            mocks["kernel32"].GetConsoleMode.return_value = False

            vt = win_vt.WindowsConsoleVT()
            with vt:
                assert vt._handle is not None
                assert vt.original_mode is None
                assert vt.enabled_by_context is False

            assert vt.enabled_by_context is False
            assert vt.original_mode is None
            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)

    def test_state_encapsulation_vt_already_enabled_no_restore(self):
        """Test when VT already enabled: enabled_by_context stays False, no restore, state preserved."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001 | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode

            vt = win_vt.WindowsConsoleVT()
            with vt:
                assert vt._handle is not None
                assert vt.original_mode == ORIGINAL_MODE
                assert vt.enabled_by_context is False

            assert vt.enabled_by_context is False
            assert vt.original_mode == ORIGINAL_MODE
            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)

    def test_state_encapsulation_enable_and_restore(self):
        """Test state transitions when enabling and restoring VT mode."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001
            EXPECTED_ENABLED_MODE = ORIGINAL_MODE | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode
            mocks["kernel32"].SetConsoleMode.return_value = True

            vt = win_vt.WindowsConsoleVT()
            assert vt.enabled_by_context is False

            with vt:
                assert vt._handle is not None
                assert vt.original_mode == ORIGINAL_MODE
                assert vt.enabled_by_context is True

            assert vt.enabled_by_context is False
            assert vt.original_mode == ORIGINAL_MODE
            assert mocks["kernel32"].SetConsoleMode.call_count == 2
            call_enable, call_restore = mocks["kernel32"].SetConsoleMode.call_args_list
            assert call_enable[0][1] == EXPECTED_ENABLED_MODE
            assert call_restore[0][1] == ORIGINAL_MODE
        finally:
            _teardown_windows_environment(mocks)

    def test_state_encapsulation_enable_failure_no_restore(self):
        """Test state when SetConsoleMode fails to enable."""
        win_vt, mocks = _setup_windows_environment()
        try:
            ORIGINAL_MODE = 0x0001

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode
            mocks["kernel32"].SetConsoleMode.return_value = False

            vt = win_vt.WindowsConsoleVT()
            with vt:
                assert vt.enabled_by_context is False

            assert vt.enabled_by_context is False
            assert vt.original_mode == ORIGINAL_MODE
            assert mocks["kernel32"].SetConsoleMode.call_count == 1
        finally:
            _teardown_windows_environment(mocks)

    def test_original_mode_preserved_when_vt_already_enabled(self):
        """Test original_mode is not cleared when VT was already enabled on entry."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0003 | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode

            vt = win_vt.WindowsConsoleVT()
            assert vt.original_mode is None

            vt.__enter__()
            assert vt.original_mode == ORIGINAL_MODE
            assert vt.enabled_by_context is False

            vt.__exit__(None, None, None)
            assert vt.original_mode == ORIGINAL_MODE
            assert vt.enabled_by_context is False

            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)

    def test_enabled_by_context_only_true_when_actually_changed(self):
        """Test enabled_by_context is only True when this context actually changed the mode."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            VT_OFF_MODE = 0x0001
            VT_ON_MODE = 0x0001 | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = VT_OFF_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode
            mocks["kernel32"].SetConsoleMode.return_value = True

            vt = win_vt.WindowsConsoleVT()
            vt.__enter__()

            assert vt.enabled_by_context is True
            assert vt.original_mode == VT_OFF_MODE
            mocks["kernel32"].SetConsoleMode.assert_called_once()
            assert mocks["kernel32"].SetConsoleMode.call_args[0][1] == VT_ON_MODE

            vt.__exit__(None, None, None)
            assert vt.enabled_by_context is False
            assert mocks["kernel32"].SetConsoleMode.call_count == 2
            assert mocks["kernel32"].SetConsoleMode.call_args_list[1][0][1] == VT_OFF_MODE
        finally:
            _teardown_windows_environment(mocks)


class TestWindowsVTProcessing:
    """Test Windows virtual terminal processing context manager."""

    def test_get_std_handle_failure(self):
        """Test GetStdHandle returning INVALID_HANDLE_VALUE - should not call SetConsoleMode."""
        win_vt, mocks = _setup_windows_environment()
        try:
            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(-1)

            with win_vt.enable_windows_virtual_terminal_processing():
                pass

            mocks["kernel32"].GetStdHandle.assert_called_once_with(-11)
            mocks["kernel32"].GetConsoleMode.assert_not_called()
            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)

    def test_get_console_mode_failure(self):
        """Test GetConsoleMode failing (returns False) - should not call SetConsoleMode."""
        win_vt, mocks = _setup_windows_environment()
        try:
            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)
            mocks["kernel32"].GetConsoleMode.return_value = False

            with win_vt.enable_windows_virtual_terminal_processing():
                pass

            mocks["kernel32"].GetStdHandle.assert_called_once_with(-11)
            mocks["kernel32"].GetConsoleMode.assert_called_once()
            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)

    def test_vt_already_enabled(self):
        """Test VT already enabled - should not call SetConsoleMode to enable or restore."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001 | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode

            with win_vt.enable_windows_virtual_terminal_processing():
                pass

            mocks["kernel32"].GetStdHandle.assert_called_once_with(-11)
            mocks["kernel32"].GetConsoleMode.assert_called_once()
            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)

    def test_vt_enable_and_restore_on_normal_exit(self):
        """Test VT enable on enter and restore original mode on normal exit."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001
            EXPECTED_ENABLED_MODE = ORIGINAL_MODE | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode
            mocks["kernel32"].SetConsoleMode.return_value = True

            with win_vt.enable_windows_virtual_terminal_processing():
                pass

            assert mocks["kernel32"].SetConsoleMode.call_count == 2
            call_enable, call_restore = mocks["kernel32"].SetConsoleMode.call_args_list
            assert call_enable[0][1] == EXPECTED_ENABLED_MODE
            assert call_restore[0][1] == ORIGINAL_MODE
        finally:
            _teardown_windows_environment(mocks)

    def test_vt_enable_and_restore_on_exception_exit(self):
        """Test VT enable on enter and restore original mode when exception is raised."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001
            EXPECTED_ENABLED_MODE = ORIGINAL_MODE | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode
            mocks["kernel32"].SetConsoleMode.return_value = True

            class TestException(Exception):
                pass

            with pytest.raises(TestException):
                with win_vt.enable_windows_virtual_terminal_processing():
                    raise TestException("simulated error")

            assert mocks["kernel32"].SetConsoleMode.call_count == 2
            call_enable, call_restore = mocks["kernel32"].SetConsoleMode.call_args_list
            assert call_enable[0][1] == EXPECTED_ENABLED_MODE
            assert call_restore[0][1] == ORIGINAL_MODE
        finally:
            _teardown_windows_environment(mocks)

    def test_vt_enable_and_restore_on_sys_exit(self):
        """Test VT enable on enter and restore original mode when sys.exit() is called."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001
            EXPECTED_ENABLED_MODE = ORIGINAL_MODE | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode
            mocks["kernel32"].SetConsoleMode.return_value = True

            with pytest.raises(SystemExit):
                with win_vt.enable_windows_virtual_terminal_processing():
                    sys.exit(-1)

            assert mocks["kernel32"].SetConsoleMode.call_count == 2
            call_enable, call_restore = mocks["kernel32"].SetConsoleMode.call_args_list
            assert call_enable[0][1] == EXPECTED_ENABLED_MODE
            assert call_restore[0][1] == ORIGINAL_MODE
        finally:
            _teardown_windows_environment(mocks)

    def test_set_console_mode_failure_no_restore(self):
        """Test SetConsoleMode failing to enable - should not attempt restore."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode
            mocks["kernel32"].SetConsoleMode.return_value = False

            with win_vt.enable_windows_virtual_terminal_processing():
                pass

            assert mocks["kernel32"].SetConsoleMode.call_count == 1
        finally:
            _teardown_windows_environment(mocks)

    def test_output_redirected_get_console_mode_fails(self):
        """Test when output is redirected (GetConsoleMode fails) - should not error."""
        win_vt, mocks = _setup_windows_environment()
        try:
            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)
            mocks["kernel32"].GetConsoleMode.return_value = False

            try:
                with win_vt.enable_windows_virtual_terminal_processing():
                    pass
            except Exception as e:
                pytest.fail(f"Should not raise exception when output redirected: {e}")

            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)

    def test_dunder_exit_restores_on_exception(self):
        """Test __exit__ restores mode even when exception is passed to it."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode
            mocks["kernel32"].SetConsoleMode.return_value = True

            vt = win_vt.WindowsConsoleVT()
            vt.__enter__()
            assert vt.enabled_by_context is True

            exit_result = vt.__exit__(ValueError, ValueError("test"), None)
            assert exit_result is None
            assert vt.enabled_by_context is False
            assert vt.original_mode == ORIGINAL_MODE
            assert mocks["kernel32"].SetConsoleMode.call_count == 2
        finally:
            _teardown_windows_environment(mocks)

    def test_no_restore_when_vt_already_enabled_exception(self):
        """Test __exit__ does NOT restore when VT was already enabled, even on exception."""
        win_vt, mocks = _setup_windows_environment()
        try:
            _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            ORIGINAL_MODE = 0x0001 | _ENABLE_VIRTUAL_TERMINAL_PROCESSING

            mocks["kernel32"].GetStdHandle.return_value = _MockHandle(123)

            def fake_get_console_mode(handle, mode_ptr):
                mode_ptr.value = ORIGINAL_MODE
                return True

            mocks["kernel32"].GetConsoleMode.side_effect = fake_get_console_mode

            vt = win_vt.WindowsConsoleVT()
            vt.__enter__()
            assert vt.enabled_by_context is False
            assert vt.original_mode == ORIGINAL_MODE

            vt.__exit__(ValueError, ValueError("test"), None)
            assert vt.enabled_by_context is False
            assert vt.original_mode == ORIGINAL_MODE
            mocks["kernel32"].SetConsoleMode.assert_not_called()
        finally:
            _teardown_windows_environment(mocks)


class TestNonWindows:
    """Test non-Windows platform behavior."""

    def test_non_windows_no_op(self):
        """Test on non-Windows platforms the context manager is a no-op."""
        with mock.patch("platform.system", return_value="Darwin"):
            if "rich_cli.win_vt" in sys.modules:
                del sys.modules["rich_cli.win_vt"]

            from rich_cli.win_vt import enable_windows_virtual_terminal_processing, WindowsConsoleVT

            try:
                vt = WindowsConsoleVT()
                assert vt.original_mode is None
                assert vt.enabled_by_context is False

                result = vt.__enter__()
                assert result is vt
                assert vt.original_mode is None
                assert vt.enabled_by_context is False

                exit_result = vt.__exit__(None, None, None)
                assert exit_result is None
                assert vt.original_mode is None
                assert vt.enabled_by_context is False

                with enable_windows_virtual_terminal_processing():
                    pass
            except Exception as e:
                pytest.fail(f"Should not raise exception on non-Windows: {e}")
            finally:
                if "rich_cli.win_vt" in sys.modules:
                    del sys.modules["rich_cli.win_vt"]
