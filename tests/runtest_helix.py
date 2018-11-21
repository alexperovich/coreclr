#!/usr/bin/env python

# This script runs tests in helix. It defines a set of test scenarios
# that enable various combinations of runtime configurations to be set
# via the test process environment.

# This script calls "corerun xunit.console.dll xunitwrapper.dll",
# where the xunitwrapper.dll will run a .sh/.cmd script per test in a
# separate process. This process will have the scenario environment
# variables set, but the xunit process will not.

# TODO: Factor out logic common with runtest.py

import argparse
import subprocess
import os
import sys

if sys.platform == "linux" or sys.platform == "darwin":
    platform_type = "unix"
elif sys.platform == "win32":
    platform_type = "windows"
else:
    print("unknown os: %s" % sys.platform)
    sys.exit(1)

class ScenarioRegistry:
    def __init__(self):
        self._runners = dict()

    def is_known_scenario_name(self, name):
        return name in self._runners

    def get_scenario_runner(self, name):
        return self._runners[name]

    def register_scenario_runner(self, name, runner):
        assert not self.is_known_scenario_name(name)
        self._runners[name] = runner

class ScenarioRunner:
    def __init__(self, name, prototype=None):
        self._name = name
        self._Core_Root = None
        self._TestEnv = dict() if prototype is None else dict(prototype._TestEnv)

    def set_COMPlus(self, name, value):
        self._TestEnv["COMPlus_" + name] = value
        return self

    def get_Core_Root(self):
        assert not self._Core_Root is None
        return self._Core_Root

    def set_Core_Root(self, dirpath):
        assert os.path.isdir(dirpath)
        self._Core_Root = dirpath

    def _get_corerun(self):
        return os.path.join(self.get_Core_Root(), "corerun" if platform_type == "unix" else "CoreRun.exe")

    def _get_console_runner(self):
        return os.path.join(self.get_Core_Root(), "xunit.console.dll")

    def _create_TestEnv(self, filepath):
        lines = []
        for name, value in self._TestEnv.items():
            lines.append("{0} {1}={2}\n".format("set" if platform_type == "windows" else "export", name, value))

        with open(filepath, "w") as f:
            f.writelines(lines)

    def _log(self, message):
        print("[%s]: %s" % (sys.argv[0], message))

    def register(self, registry):
        registry.register_scenario_runner(self._name, self)

    def run(self, test_wrapper_filepath):
        assert os.path.isfile(test_wrapper_filepath)

        args = [
            self._get_corerun(),
            self._get_console_runner(),
            test_wrapper_filepath,
            "-nocolor",
            "-noshadow",
            "-xml", "testResults.xml",
            "-notrait", "category=outerloop",
            "-notrait", "category=failing",
            "-parallel", "collections"]

        environ = dict(os.environ)
        environ["CORE_ROOT"] = self.get_Core_Root()
        self._log("CORE_ROOT=%s" % self.get_Core_Root())

        env_script_filepath = os.path.join(os.getcwd(), "SetStressModes.bat")
        environ["__TestEnv"] = env_script_filepath

        self._log("Creating __TestEnv at {0}".format(env_script_filepath))
        self._create_TestEnv(env_script_filepath)

        self._log("BEGIN EXECUTION")
        self._log(" ".join(args))

        proc = subprocess.Popen(args, env=environ)
        proc.communicate()

        self._log("Finished running tests. Exit code = %d" % proc.returncode)
        return proc.returncode

def build_registry():
    registry = ScenarioRegistry()

    baseline = ScenarioRunner("baseline") \
        .set_COMPlus("TieredCompilation", "0")

    baseline.register(registry)

    # Jit Stress Scenarios

    ScenarioRunner("jitstress1", baseline) \
        .set_COMPlus("JitStress", "1") \
        .register(registry)

    ScenarioRunner("jitstress2", baseline) \
        .set_COMPlus("JitStress", "2") \
        .register(registry)

    ScenarioRunner("jitstress1_tiered") \
        .set_COMPlus("JitStress", "2") \
        .set_COMPlus("TieredCompilation", "1") \
        .register(registry)

    ScenarioRunner("jitstress2_tiered") \
        .set_COMPlus("JitStress", "2") \
        .set_COMPlus("TieredCompilation", "1") \
        .register(registry)

    # GC Stress Scenarios

    ScenarioRunner("gcstress0x3", baseline) \
        .set_COMPlus("COMPlus_GCStress", "0x3") \
        .register(registry)

    ScenarioRunner("gcstress0xc", baseline) \
        .set_COMPlus("COMPlus_GCStress", "0xc") \
        .register(registry)

    return registry

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse arguments")
    parser.add_argument("-scenario", dest="scenario", default="baseline")
    parser.add_argument("-wrapper", dest="wrapper", required=True)

    args = parser.parse_args()

    scenario = args.scenario

    registry = build_registry()

    if not registry.is_known_scenario_name(scenario):
        print("Scenario \"%s\" is unknown" % scenario)
        sys.exit(1)

    if not "HELIX_CORRELATION_PAYLOAD" in os.environ:
        print("HELIX_CORRELATION_PAYLOAD must be defined in environment")
        sys.exit(1)

    if not "HELIX_WORKITEM_PAYLOAD" in os.environ:
        print("HELIX_WORKITEM_PAYLOAD must be defined in environment")
        sys.exit(1)

    test_wrapper_filepath = os.path.join(os.environ["HELIX_WORKITEM_PAYLOAD"], args.wrapper)

    runner = registry.get_scenario_runner(scenario)
    runner.set_Core_Root(os.environ["HELIX_CORRELATION_PAYLOAD"])

    returncode = runner.run(test_wrapper_filepath)
    sys.exit(returncode)
