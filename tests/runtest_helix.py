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
        self._scenarios = dict()

    def contains(self, name):
        return name in self._scenarios

    def registerScenario(self, name, scenario):
        self._scenarios[name] = scenario

    def createRunner(self, name):
        assert name in self._scenarios
        scenario = self._scenarios[name]
        return  ScenarioRunner(scenario)

class Scenario:
    def __init__(self, name):
        self._name = name
        self._environ = dict()

    def prototype(self, prototype):
        for name,value in prototype._environ.items():
            self._environ[name] = value
        return self

    def _setEnviron(self, name, value):
        self._environ[name] = value

    def setForceRelocs(self, forceRelocs):
        self._setEnviron("COMPlus_ForceRelocs", forceRelocs)
        return self

    def setGCStress(self, gcStress):
        self._setEnviron("COMPlus_GCStress", gcStress)
        return self

    def setHeapVerify(self, heapVerify):
        self._setEnviron("COMPlus_HeapVerify", "1")
        return self

    def setJITMinOpts(self, JITMinOpts):
        self._setEnviron("COMPlus_JITMinOpts", JITMinOpts)
        return self

    def setJitStress(self, jitStress):
        self._setEnviron("COMPlus_JitStress", jitStress)
        return self

    def setJitStressRegs(self, jitStressRegs):
        self._setEnviron("COMPlus_JitStressRegs", jitStressRegs)
        return self

    def setReadyToRun(self, readyToRun):
        self._setEnviron("COMPlus_ReadyToRun", readyToRun)
        return self

    def setRunCrossGen(self, runCrossGen):
        self._setEnviron("RunCrossGen", runCrossGen)
        return self

    def setTailcallStress(self, tailcallStress):
        self._setEnviron("COMPlus_TailcallStress", tailcallStress)
        return self

    def setTieredCompilation(self, tieredCompilation):
        self._setEnviron("COMPlus_TieredCompilation", tieredCompilation)
        return self

    def setZapDisable(self, zapDisable):
        self._setEnviron("COMPlus_ZapDisable", zapDisable)
        return self

    def register(self, registry):
        registry.registerScenario(self._name, self)

class ScenarioRunner:
    def __init__(self, scenario):
        self._scenario = scenario

    def setCoreRoot(self, coreRoot):
        self._CoreRoot = coreRoot

    def _getCoreRun(self):
        return os.path.join(self._CoreRoot, "corerun" if platform_type == "unix" else "CoreRun.exe")

    def _getTestRunner(self):
        return os.path.join(self._CoreRoot, "xunit.console.dll")

    def _buildArgs(self, testsWrapper):
        return [
            self._getCoreRun(),
            self._getTestRunner(),
            testsWrapper,
            "-nocolor",
            "-noshadow",
            "-xml", "testResults.xml",
            "-notrait", "category=outerloop",
            "-notrait", "category=failing",
            "-parallel", "collections"]

    def _buildSetEnvCommand(self, tup):
        name, value = tup
        if platform_type == "windows":
            return "set {0}={1}".format(name, value)
        else:
            return "export {0}={1}".format(name, value)

    def _createTestEnvFile(self, path):
        lines = map(self._buildSetEnvCommand, self._scenario._environ.items())

        self._log("Creating __TestEnv at {0} with contents:".format(path))
        for line in lines:
            self._log(" " + line)
        with open(path, "w") as testEnvFile:
            contents = "\n".join(lines)
            testEnvFile.writelines(contents)

    def _log(self, message):
        print("[%s]: %s" % (sys.argv[0], message))

    def run(self, testsWrapperPath):
        assert os.path.isfile(testsWrapperPath)
        
        args = self._buildArgs(testsWrapperPath)

        environ = dict(os.environ)
        environ["CORE_ROOT"] = self._CoreRoot

        self._log("CORE_ROOT=%s" % self._CoreRoot)

        testEnvPath = os.path.join(os.path.dirname(testsWrapperPath), "SetStressModes.bat" if platform_type == "windows" else "SetStressModes.sh")
        self._createTestEnvFile(testEnvPath)
        environ["__TestEnv"] = testEnvPath
        
        self._log("BEGIN EXECUTION")
        self._log(" ".join(args))

        proc = subprocess.Popen(args, env=environ)
        proc.communicate()

        self._log("Finished running tests. Exit code = %d" % proc.returncode)
        return proc.returncode

def buildJitStressScenarios(registry):
    baseline = Scenario("no_tiered_compilation") \
        .setTieredCompilation("0")
    baseline.register(registry)

    Scenario("minopts") \
        .prototype(baseline) \
        .setJITMinOpts("1") \
        .register(registry)

    Scenario("tieredcompilation") \
        .setTieredCompilation("1") \
        .register(registry)

    Scenario("forcerelocs") \
        .setForceRelocs("1") \
        .register(registry)

    Scenario("jitstress1") \
        .prototype(baseline) \
        .setJitStress("1") \
        .register(registry)
    
    Scenario("jitstress2") \
        .prototype(baseline) \
        .setJitStress("2") \
        .register(registry)

    Scenario("jitstress1_tiered") \
        .setJitStress("2") \
        .setTieredCompilation("1") \
        .register(registry)

    Scenario("jitstress2_tiered") \
        .setJitStress("2") \
        .setTieredCompilation("1") \
        .register(registry)

    Scenario("jitstressregs1") \
        .prototype(baseline) \
        .setJitStressRegs("1") \
        .register(registry)

    Scenario("jitstressregs2") \
        .prototype(baseline) \
        .setJitStressRegs("2") \
        .register(registry)

    Scenario("jitstressregs3") \
        .prototype(baseline) \
        .setJitStressRegs("3") \
        .register(registry)

    Scenario("jitstressregs4") \
        .prototype(baseline) \
        .setJitStressRegs("4") \
        .register(registry)

    Scenario("jitstressregs8") \
        .prototype(baseline) \
        .setJitStressRegs("8") \
        .register(registry)

    Scenario("jitstressregs0x10") \
        .prototype(baseline) \
        .setJitStressRegs("0x10") \
        .register(registry)

    Scenario("jitstressregs0x80") \
        .prototype(baseline) \
        .setJitStressRegs("0x80") \
        .register(registry)

    Scenario("jitstressregs0x1000") \
        .prototype(baseline) \
        .setJitStressRegs("0x1000") \
        .register(registry)

    Scenario("jitstress2_jitstressregs1") \
        .prototype(baseline) \
        .setJitStress("2") \
        .setJitStressRegs("1") \
        .register(registry)

    Scenario("jitstress2_jitstressregs2") \
        .prototype(baseline) \
        .setJitStress("2") \
        .setJitStressRegs("2") \
        .register(registry)

    Scenario("jitstress2_jitstressregs3") \
        .prototype(baseline) \
        .setJitStress("2") \
        .setJitStressRegs("3") \
        .register(registry)

    Scenario("jitstress2_jitstressregs4") \
        .prototype(baseline) \
        .setJitStress("2") \
        .setJitStressRegs("4") \
        .register(registry)

    Scenario("jitstress2_jitstressregs8") \
        .prototype(baseline) \
        .setJitStress("2") \
        .setJitStressRegs("8") \
        .register(registry)

    Scenario("jitstress2_jitstressregs0x10") \
        .prototype(baseline) \
        .setJitStress("2") \
        .setJitStressRegs("0x10") \
        .register(registry)

    Scenario("jitstress2_jitstressregs0x80") \
        .prototype(baseline) \
        .setJitStress("2") \
        .setJitStressRegs("0x80") \
        .register(registry)

    Scenario("jitstress2_jitstressregs0x1000") \
        .prototype(baseline) \
        .setJitStress("2") \
        .setJitStressRegs("0x1000") \
        .register(registry)

    Scenario("tailcallstress") \
        .prototype(baseline) \
        .setTailcallStress("1") \
        .register(registry)

def buildGcStressScenarios(registry):
    baseline = Scenario("baseline") \
        .setTieredCompilation("0")

    Scenario("gcstress0x3") \
        .prototype(baseline) \
        .setGCStress("0x3") \
        .register(registry)

    Scenario("gcstress0xc") \
        .prototype(baseline) \
        .setGCStress("0xc") \
        .register(registry)

    Scenario("zapdisable") \
        .prototype(baseline) \
        .setZapDisable("1") \
        .setReadyToRun("0") \
        .register(registry)

    Scenario("heapverify1") \
        .prototype(baseline) \
        .setHeapVerify("1") \
        .register(registry)

    Scenario("gcstress0xc_zapdisable") \
        .prototype(baseline) \
        .setGCStress("0xc") \
        .setZapDisable("1") \
        .register(registry)

    Scenario("gcstress0xc_zapdisable_jitstress2") \
        .prototype(baseline) \
        .setGCStress("0xc") \
        .setZapDisable("1") \
        .setJitStress("2") \
        .register(registry)

    Scenario("gcstress0xc_zapdisable_heapverify1") \
        .prototype(baseline) \
        .setGCStress("0xc") \
        .setZapDisable("1") \
        .setHeapVerify("1") \
        .register(registry)

    Scenario("gcstress0xc_jitstress1") \
        .prototype(baseline) \
        .setGCStress("0xc") \
        .setJitStress("1") \
        .register(registry)

    Scenario("gcstress0xc_jitstress2") \
        .prototype(baseline) \
        .setGCStress("0xc") \
        .setJitStress("2") \
        .register(registry)

    Scenario("gcstress0xc_minopts_heapverify1") \
        .prototype(baseline) \
        .setGCStress("0xc") \
        .setJITMinOpts("1") \
        .setHeapVerify("1") \
        .register(registry)

def buildReadyToRunStressScenarios(registry):
    baseline = Scenario("r2r_no_tiered_compilation") \
        .setTieredCompilation("0") \
        .setReadyToRun("1")
    baseline.register(registry)

    Scenario("r2r_jitstress1") \
        .prototype(baseline) \
        .setJitStress("1") \
        .register(registry)

    Scenario("r2r_jitstress2") \
        .prototype(baseline) \
        .setJitStress("2") \
        .register(registry)

    Scenario("r2r_jitstress1_tiered") \
        .setReadyToRun("1") \
        .setJitStress("1") \
        .setTieredCompilation("1") \
        .register(registry)

    Scenario("r2r_jitstress2_tiered") \
        .setReadyToRun("1") \
        .setJitStress("2") \
        .setTieredCompilation("1") \
        .register(registry)

    Scenario("r2r_jitstressregs1") \
        .prototype(baseline) \
        .setJitStressRegs("1") \
        .register(registry)

    Scenario("r2r_jitstressregs2") \
        .prototype(baseline) \
        .setJitStressRegs("2") \
        .register(registry)

    Scenario("r2r_jitstressregs3") \
        .prototype(baseline) \
        .setJitStressRegs("3") \
        .register(registry)

    Scenario("r2r_jitstressregs4") \
        .prototype(baseline) \
        .setJitStressRegs("4") \
        .register(registry)

    Scenario("r2r_jitstressregs8") \
        .prototype(baseline) \
        .setJitStressRegs("8") \
        .register(registry)

    Scenario("r2r_jitstressregs0x10") \
        .prototype(baseline) \
        .setJitStressRegs("0x10") \
        .register(registry)

    Scenario("r2r_jitstressregs0x80") \
        .prototype(baseline) \
        .setJitStressRegs("0x80") \
        .register(registry)

    Scenario("r2r_jitstressregs0x1000") \
        .prototype(baseline) \
        .setJitStressRegs("0x1000") \
        .register(registry)

    Scenario("r2r_jitminopts") \
        .prototype(baseline) \
        .setJITMinOpts("1") \
        .register(registry)

    Scenario("r2r_jitforcerelocs") \
        .prototype(baseline) \
        .setForceRelocs("1") \
        .register(registry)

    Scenario("r2r_gcstress15") \
        .prototype(baseline) \
        .setGCStress("0xF") \
        .register(registry)

    return registry

def buildScenarioRegistry():
    registry = ScenarioRegistry()

    buildJitStressScenarios(registry)
    buildGcStressScenarios(registry)
    buildReadyToRunStressScenarios(registry)

    return registry

if __name__ == "__main__":
    registry = buildScenarioRegistry()

    parser = argparse.ArgumentParser(description="Parse arguments")
    parser.add_argument("-scenario", dest="scenario", default="baseline")
    parser.add_argument("-wrapper", dest="wrapper", required=True)

    args = parser.parse_args()

    scenario = args.scenario

    if not registry.contains(scenario):
        print("Scenario \"%s\" is unknown" % scenario)
        sys.exit(1)

    if not "HELIX_CORRELATION_PAYLOAD" in os.environ:
        print("HELIX_CORRELATION_PAYLOAD must be defined in environment")
        sys.exit(1)

    if not "HELIX_WORKITEM_PAYLOAD" in os.environ:
        print("HELIX_WORKITEM_PAYLOAD must be defined in environment")
        sys.exit(1)

    testsWrapperPath = os.path.join(os.environ["HELIX_WORKITEM_PAYLOAD"], args.wrapper)

    runner = registry.createRunner(scenario)
    runner.setCoreRoot(os.environ["HELIX_CORRELATION_PAYLOAD"])
    returncode = runner.run(testsWrapperPath)

    sys.exit(returncode)
