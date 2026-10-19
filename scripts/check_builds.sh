#!/usr/bin/env bash
# Week-1 gate, build part: each pinned project compiles and one of its smelly test classes passes, unmodified.
set -uo pipefail
cd "$(dirname "$0")/.."
export JAVA_HOME=${JAVA_HOME_17:-/usr/lib/jvm/java-17-openjdk-amd64}; export PATH=$JAVA_HOME/bin:$PATH
mvn -v | head -1; java -version 2>&1 | head -1
SKIP="-Denforcer.skip=true -Drat.skip=true -Dcheckstyle.skip=true -Dspotbugs.skip=true -Dpmd.skip=true -Danimal.sniffer.skip=true -Djapicmp.skip=true -Dmaven.javadoc.skip=true -Djacoco.skip=true -Dspotless.check.skip=true -Drevapi.skip=true -Dbnd.skip=true -Dmoditect.skip=true"
run() { ( cd "$1" && mvn -q -B test -Dtest="$2" -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false $SKIP ) >/tmp/check_$2.log 2>&1; echo "$1 $2 EXIT=$? (log /tmp/check_$2.log)"; }
run data/projects/commons-cli ValueTest
run data/projects/gson/gson JsonArrayAsListTest
run data/projects/jsoup NodeTest
