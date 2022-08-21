# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2022 Valory AG
#   Copyright 2018-2021 Fetch.AI Limited
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------
"""This test module contains the tests for CLI test command."""
import subprocess  # nosec
from pathlib import Path
from textwrap import dedent
from typing import Any, Sequence, Type
from unittest import mock

import click.testing
import pytest
from _pytest.config import ExitCode

from aea.cli import cli
from aea.cli.utils.package_utils import get_package_path
from aea.configurations.data_types import ComponentType, PublicId
from aea.helpers.base import cd
from aea.test_tools.test_cases import AEATestCaseEmpty, CLI_LOG_OPTION


OK_PYTEST_EXIT_CODE = ExitCode.OK
NO_TESTS_COLLECTED_PYTEST_EXIT_CODE = ExitCode.NO_TESTS_COLLECTED


def _parametrize_class(test_cls: Type) -> Type:
    """Allow a base AEA test class to use 'setup/teardown' instead of '(setup/teardown)_class' methods."""
    old_setup_class = test_cls.setup_class
    old_teardown_class = test_cls.teardown_class

    def setup_class(cls) -> None:
        """Don't call super setup method."""

    def teardown_class(cls) -> None:
        """Don't call super teardown method."""

    def setup(self) -> None:
        """Setup after every test execution."""
        old_setup_class()  # type: ignore

    def teardown(self) -> None:
        """Tear down after every test execution."""
        old_teardown_class()  # type: ignore

    test_cls.setup_class = setup_class
    test_cls.teardown_class = teardown_class
    test_cls.setup = setup
    test_cls.teardown = teardown

    return test_cls


def mock_pytest_main() -> Any:
    """
    Mock pytest main so to run in a subprocess.

    This is necessary as otherwise the in-process subcall to pytest will conflict with the current pytest runtime.
    """

    def fun(args) -> int:
        result = subprocess.call(["pytest", *args])  # nosec
        return result

    return mock.patch("aea.cli.test.pytest.main", side_effect=fun)


class BaseAEATestCommand(AEATestCaseEmpty):
    """Base class for tests related to the command `aea test`."""

    @classmethod
    def run_test_command(cls, *args: Sequence[str]) -> click.testing.Result:
        """
        Execute an 'aea test' command.

        It differs from the method run_cli_command of the base class as it does not
        raise exception when the executed CLI command fails.

        :param args: the argumnets to pass to `aea test`
        :return: the click.testing.Result object
        """
        with cd(cls._get_cwd()):
            return cls.runner.invoke(
                cli,
                [*CLI_LOG_OPTION, "test", *args],
                standalone_mode=False,
                catch_exceptions=False,
            )

    def test_aea_dirpath(self) -> Path:
        """Get the test AEA directory path."""
        return self.t / self.agent_name / "tests"

    def dummy_package_dirpath(
        self, package_type: ComponentType, item_name: str
    ) -> Path:
        """
        Get the package directory path.

        :param package_type: the type of the package
        :param item_name: the name of the item
        :return: path to the AEA package
        """
        public_id = self._public_id(package_type)
        result = get_package_path(
            self.t / self.agent_name,
            str(package_type.value),
            public_id,
            is_vendor=False,
        )
        return Path(result)

    def get_test_package_dirpath(
        self, package_type: ComponentType, item_name: str
    ) -> Path:
        """
        Get the test package directory path.

        :param package_type: the type of the package
        :param item_name: the name of the item
        :return: path to the AEA package
        """
        return self.dummy_package_dirpath(package_type, item_name) / "tests"

    @classmethod
    def write_dummy_test_module(cls, path_to_module: Path) -> None:
        """Write dummy test module."""
        path_to_module.write_text(
            dedent(
                """\
        def test_dummy_function():
            assert True
        """
            )
        )

    @classmethod
    def _get_dummy_package_name(cls, package_type: ComponentType) -> str:
        """Get the name of the dummy package from package type."""
        return f"dummy_{package_type.value}"

    def _scaffold_item(self, package_type: ComponentType) -> None:
        """Scaffold an item for testing."""
        self.scaffold_item(
            str(package_type.value), self._get_dummy_package_name(package_type)
        )

    def _public_id(self, package_type: ComponentType) -> PublicId:
        """Return the PublicId of the dummy package."""
        return PublicId(self.author, self._get_dummy_package_name(package_type))

    def _configure_package_for_testing(self, package_type: ComponentType) -> None:
        """Configure a package for testing."""
        self._scaffold_item(package_type)
        test_package_name = self._get_dummy_package_name(package_type)
        test_package_dirpath = self.get_test_package_dirpath(
            package_type, test_package_name
        )
        test_package_dirpath.mkdir(exist_ok=False)
        test_module_filepath = (
            test_package_dirpath / f"test_{package_type.value}_module.py"
        )
        self.write_dummy_test_module(test_module_filepath)
        self.fingerprint_item(
            str(package_type.value), str(self._public_id(package_type))
        )


class TestAgentTestEmptySuite(BaseAEATestCommand):
    """Test that the command 'aea test' works as expected (with an empty test suite)."""

    def test_exit_code_equal_to_5(self):
        """Assert that the exit code is equal to 5 (i.e. pytest succeeds without collecting tests)."""
        result = self.run_test_command()
        assert result.exit_code == NO_TESTS_COLLECTED_PYTEST_EXIT_CODE


class TestAgentTestSingleTest(BaseAEATestCommand):
    """Test that the command 'aea test' works as expected (with a non-empty test suite)."""

    def test_run(self):
        """Assert that the exit code is equal to 0 (tests are run successfully)."""
        # write dummy test module in test/ folder
        self.test_aea_dirpath().mkdir(exist_ok=False)
        test_module_filepath = self.test_aea_dirpath() / "test_module.py"
        self.write_dummy_test_module(test_module_filepath)
        result = self.run_test_command()
        assert result.exit_code == OK_PYTEST_EXIT_CODE


@_parametrize_class
class TestPackageTestByTypeEmptyTestSuite(BaseAEATestCommand):
    """Test that the command 'aea test item_type public_id' works as expected (with an empty test suite)."""

    @pytest.mark.parametrize("package_type", list(ComponentType))
    def test_run(self, package_type: ComponentType):
        """Assert that the exit code is equal to 5 (empty test suite)."""
        self._scaffold_item(package_type)
        public_id = self._public_id(package_type)
        result = self.run_test_command(str(package_type.value), str(public_id))
        assert result.exit_code == NO_TESTS_COLLECTED_PYTEST_EXIT_CODE


@_parametrize_class
class TestPackageTestByType(BaseAEATestCommand):
    """Test that the command 'aea test item_type public_id' works as expected (with a non-empty test suite)."""

    @pytest.mark.parametrize("package_type", list(ComponentType))
    def test_run(self, package_type: ComponentType, *_mocks: Any):
        """Assert that the exit code is equal to 0 (tests are run successfully)."""
        self._configure_package_for_testing(package_type)
        public_id = self._public_id(package_type)
        with mock_pytest_main():
            result = self.run_test_command(str(package_type.value), str(public_id))
            assert result.exit_code == OK_PYTEST_EXIT_CODE


@_parametrize_class
class TestPackageTestByPathEmptyTestSuite(BaseAEATestCommand):
    """Test that the command 'aea test by-path path-to-package' works as expected (empty test suite)."""

    @pytest.mark.parametrize("package_type", list(ComponentType))
    def test_run(self, package_type: ComponentType):
        """Assert that the exit code is equal to 0 (tests are run successfully)."""
        self._scaffold_item(package_type)
        test_package_name = self._get_dummy_package_name(package_type)
        package_dirpath = self.dummy_package_dirpath(package_type, test_package_name)
        with mock_pytest_main():
            result = self.run_test_command("by-path", str(package_dirpath))
            assert result.exit_code == NO_TESTS_COLLECTED_PYTEST_EXIT_CODE


@_parametrize_class
class TestPackageTestByPath(BaseAEATestCommand):
    """Test that the command 'aea test by-path path-to-package' works as expected (non-empty test suite)."""

    @pytest.mark.parametrize("package_type", list(ComponentType))
    def test_run(self, package_type: ComponentType, *_mocks: Any):
        """Assert that the exit code is equal to 0 (tests are run successfully)."""
        self._configure_package_for_testing(package_type)
        test_package_name = self._get_dummy_package_name(package_type)
        package_dirpath = self.dummy_package_dirpath(package_type, test_package_name)
        with mock_pytest_main():
            result = self.run_test_command("by-path", str(package_dirpath))
            assert result.exit_code == OK_PYTEST_EXIT_CODE
